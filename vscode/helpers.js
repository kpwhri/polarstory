'use strict';

const fs = require('node:fs');
const path = require('node:path');

function resolveSetting(value, workspace) {
    if (!value) return undefined;
    return path.isAbsolute(value) ? path.normalize(value) : path.resolve(workspace, value);
}

function uniqueOutput(source, extension) {
    const parsed = path.parse(source);
    const base = path.join(parsed.dir, `${parsed.name}.${extension}.html`);
    if (!fs.existsSync(base)) return base;
    for (let count = 2; count < 10000; count += 1) {
        const candidate = path.join(parsed.dir, `${parsed.name}.${extension}-${count}.html`);
        if (!fs.existsSync(candidate)) return candidate;
    }
    throw new Error('No available output path');
}

function createArgs(action, source, output, config, diagnostic) {
    const args = ['-m', 'polarstory'];
    if (action === 'inspect') {
        args.push('inspect', source, '-o', output);
    } else if (action === 'advanced') {
        const kinds = ['missingness', 'numeric', 'categorical', 'quality', 'associations'];
        if (!kinds.includes(diagnostic)) throw new Error(`Unknown diagnostic type: ${diagnostic}`);
        args.push('diagnose', source, '--type', diagnostic, '-o', output, '--no-open', '--progress');
    } else {
        if (!['quick', 'standard', 'full'].includes(action)) {
            throw new Error(`Unsupported profiling mode: ${action}`);
        }
        args.push('profile', source, '--mode', action, '-o', output, '--no-open', '--progress');
    }
    if (config) args.push('--config', config);
    return args;
}

module.exports = {resolveSetting, uniqueOutput, createArgs};
