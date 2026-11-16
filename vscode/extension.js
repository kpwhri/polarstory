'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {resolveSetting, uniqueOutput, createArgs} = require('./helpers');

let output;

async function interpreter(uri, folder, settings) {
    const override = resolveSetting(settings.get('pythonPath'), folder);
    if (override) {
        if (!fs.existsSync(override)) throw new Error(`Configured Python not found: ${override}`);
        return override;
    }
    const extension = vscode.extensions.getExtension('ms-python.python');
    if (extension) {
        const api = extension.isActive ? extension.exports : await extension.activate();
        const environments = api && api.environments;
        if (environments) {
            const selected = environments.getActiveEnvironmentPath(uri);
            if (selected) {
                const detail = await environments.resolveEnvironment(selected);
                const executable = detail && detail.executable && detail.executable.uri;
                if (executable && executable.scheme === 'file' && fs.existsSync(executable.fsPath)) {
                    return executable.fsPath;
                }
            }
        }
    }
    throw new Error('No Python interpreter resolved. Select a Python environment in VS Code or set polarstory.pythonPath.');
}

function runPython(python, args, cwd, token) {
    return new Promise((resolve, reject) => {
        const child = spawn(python, args, {cwd, shell: false, windowsHide: true});
        let stdout = '';
        let stderr = '';
        const cancel = token.onCancellationRequested(() => child.kill());
        child.stdout.setEncoding('utf8');
        child.stderr.setEncoding('utf8');
        child.stdout.on('data', text => {
            stdout += text;
            output.append(text);
        });
        child.stderr.on('data', text => {
            stderr += text;
            output.append(text);
        });
        child.on('error', error => {
            cancel.dispose();
            reject(error);
        });
        child.on('close', code => {
            cancel.dispose();
            if (token.isCancellationRequested) return reject(new Error('Profiling cancelled'));
            if (code !== 0) return reject(new Error(`polarstory exited with code ${code}: ${stderr.trim() || stdout.trim()}`));
            resolve(stdout);
        });
    });
}

const diagnostics = [
    {
        label: 'Missing Data Analysis', value: 'missingness',
        description: 'Patterns, missingness relationships, and overview'
    },
    {
        label: 'Numeric Diagnostics', value: 'numeric',
        description: 'Distributions, quantiles, and IQR outliers'
    },
    {
        label: 'Categorical Diagnostics', value: 'categorical',
        description: 'Frequencies, rarity, and dominance'
    },
    {
        label: 'Data Quality Analysis', value: 'quality',
        description: 'Alerts, duplicates, and uniqueness'
    },
    {
        label: 'Variable Relationships', value: 'associations',
        description: 'Descriptive numeric correlations'
    }
];

async function invoke(action, selected) {
    if (!vscode.workspace.isTrusted) {
        vscode.window.showWarningMessage('Trust this workspace before running polarstory.');
        return;
    }
    const uri = selected || (vscode.window.activeTextEditor && vscode.window.activeTextEditor.document.uri);
    if (!uri || uri.scheme !== 'file' || path.extname(uri.fsPath).toLowerCase() !== '.parquet') {
        vscode.window.showWarningMessage('Select a local .parquet file in the Explorer.');
        return;
    }
    const workspace = vscode.workspace.getWorkspaceFolder(uri);
    const cwd = workspace ? workspace.uri.fsPath : path.dirname(uri.fsPath);
    const settings = vscode.workspace.getConfiguration('polarstory', uri);
    output.show(true);
    try {
        let diagnostic;
        if (action === 'advanced') {
            const chosen = await vscode.window.showQuickPick(diagnostics, {
                placeHolder: 'Choose the diagnostic report to generate'
            });
            if (!chosen) return;
            diagnostic = chosen.value;
        }
        const python = await interpreter(uri, cwd, settings);
        const report = uniqueOutput(uri.fsPath, action === 'inspect' ? 'inspect' :
            (diagnostic || 'profile'));
        const config = resolveSetting(settings.get('configFile'), cwd);
        if (config && !fs.existsSync(config)) throw new Error(`Configuration not found: ${config}`);
        const args = createArgs(action, uri.fsPath, report, config, diagnostic);
        output.appendLine(`Running: ${python} -m polarstory ${action} for ${uri.fsPath}`);
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `polarstory: ${action} ${path.basename(uri.fsPath)}`,
            cancellable: true
        }, (_progress, token) => runPython(python, args, cwd, token));
        if (!fs.existsSync(report)) throw new Error(`polarstory finished without writing ${report}`);
        const view = 'Open report';
        const chosen = await vscode.window.showInformationMessage(
            `polarstory generated ${path.basename(report)}`, view
        );
        if (settings.get('openReport') || chosen === view) {
            await vscode.env.openExternal(vscode.Uri.file(report));
        }
    } catch (error) {
        output.appendLine(String(error));
        vscode.window.showErrorMessage(`polarstory: ${error.message || error}. See Output → polarstory.`);
    }
}

function activate(context) {
    output = vscode.window.createOutputChannel('polarstory');
    context.subscriptions.push(output);
    for (const [command, action] of [
        ['polarstory.inspect', 'inspect'],
        ['polarstory.profileQuick', 'quick'],
        ['polarstory.profileStandard', 'standard'],
        ['polarstory.profileFull', 'full'],
        ['polarstory.advanced', 'advanced']
    ]) {
        context.subscriptions.push(vscode.commands.registerCommand(command, uri => invoke(action, uri)));
    }
}

function deactivate() {
}

module.exports = {activate, deactivate};
