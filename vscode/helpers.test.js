'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const {createArgs, resolveSetting, uniqueOutput} = require('./helpers');

test('argument arrays preserve paths with spaces', () => {
    const args = createArgs('standard', 'C:\\Project Folder\\cohort.parquet', 'C:\\Output Folder\\report.html');
    assert.deepEqual(args.slice(0, 4), ['-m', 'polarstory', 'profile', 'C:\\Project Folder\\cohort.parquet']);
    assert.equal(args.includes('--progress'), true);
});

test('inspection passes a named output and config', () => {
    const args = createArgs('inspect', '/tmp/data.parquet', '/tmp/inspect.html', '/tmp/polarstory.toml');
    assert.deepEqual(args, ['-m', 'polarstory', 'inspect', '/tmp/data.parquet', '-o', '/tmp/inspect.html', '--config', '/tmp/polarstory.toml']);
});

test('unique output preserves the source filename', () => {
    const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'polarstory-vscode-'));
    try {
        const source = path.join(folder, 'my cohort.parquet');
        const first = uniqueOutput(source, 'profile');
        fs.writeFileSync(first, 'old report');
        assert.notEqual(uniqueOutput(source, 'profile'), first);
    } finally {
        fs.rmSync(folder, {recursive: true, force: true});
    }
});

test('relative workspace settings', () => {
    assert.equal(resolveSetting('config/polarstory.toml', '/test'), path.resolve('/test', 'config/polarstory.toml'));
});

test('advanced diagnostics passes a selected preset without shell interpolation', () => {
    const args = createArgs('advanced', 'C:\\Studies Folder\\data.parquet', 'C:\\Output Folder\\data.numeric.html', undefined, 'numeric');
    assert.deepEqual(args.slice(0, 4), ['-m', 'polarstory', 'diagnose', 'C:\\Studies Folder\\data.parquet']);
    assert.equal(args.includes('--type'), true);
    assert.equal(args[args.indexOf('--type') + 1], 'numeric');
    assert.throws(() => createArgs('advanced', 'a.parquet', 'a.html', undefined, 'other'));
});

test('explorer commands appear in a polarstory submenu', () => {
    const manifest = require('./package.json');
    assert.equal(manifest.contributes.submenus[0].id, 'polarstory.parquetMenu');
    const menu = manifest.contributes.menus['explorer/context'];
    assert.equal(menu.length, 1);
    assert.equal(menu[0].submenu, 'polarstory.parquetMenu');
    assert.equal(manifest.contributes.menus['polarstory.parquetMenu'].length, 5);
});
