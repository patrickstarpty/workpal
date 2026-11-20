import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn, execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

// Resolve from this file, so npm --prefix and repository-root invocations agree.
const repo = fileURLToPath(new URL('../../../', import.meta.url));
const python = path.join(repo, '.venv-workpal/bin/python');
const manage = path.join(repo, 'services/workpal/manage.py');

export async function withBrowser(run) {
  const require = createRequire(import.meta.url);
  let pw;
  for (const name of [process.env.WORKPAL_PLAYWRIGHT, '@playwright/test', '/Users/patrick/.codex/worktrees/tapper-agent-workflows/tap/deploy/browser/node_modules/@playwright/test/index.js'].filter(Boolean)) {
    try { const mod = await import(pathToFileURL(require.resolve(name))); pw = mod.default ?? mod; break; } catch {}
  }
  if (!pw) throw Error('Playwright unavailable');
  const dir = await mkdtemp(path.join(tmpdir(), 'workpal-browser-'));
  const env = {...process.env, WORKPAL_ENV:'development', WORKPAL_DB_PATH:path.join(dir, 'qa.sqlite3'), WORKPAL_SECRET_KEY:'isolated-browser-check-only', DJANGO_SETTINGS_MODULE:'config.settings'};
  const runPython = code => execFileSync(python, [manage, 'shell', '-c', code], {cwd:repo, env, encoding:'utf8', stdio:['ignore','pipe','pipe']});
  let server, browser;
  let logs = ""; const pages = [], diagnostics = [];
  const errors = [], external = [];
  try {
    execFileSync(python, [manage, 'migrate', '--noinput'], {cwd:repo, env, stdio:'pipe'});
    runPython("from django.contrib.auth import get_user_model; from workpal.identity.models import Workspace, Membership; u=get_user_model().objects.create_user(username='owner',password='qa-password'); m=get_user_model().objects.create_user(username='reader',password='qa-password'); a=Workspace.objects.create(name='First'); b=Workspace.objects.create(name='Second'); Membership.objects.create(user=u,workspace=a,role='owner'); Membership.objects.create(user=u,workspace=b,role='owner'); Membership.objects.create(user=m,workspace=a,role='member')");
    // Bind port zero in the serving process itself. Readiness comes only from
    // our child; an unrelated listener can never satisfy this handshake.
    server = spawn(python, ['-u', '-c', `
from django.core.wsgi import get_wsgi_application
from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    # Isolated browser QA opens concurrent module connections across contexts.
    # Default TCPServer backlog 5 reproduced socket failures in qa.startup.
    request_queue_size = 128
server = make_server('127.0.0.1', 0, get_wsgi_application(), server_class=Server)
print('WORKPAL_READY:' + str(server.server_port), flush=True)
server.serve_forever()
`], {cwd:path.join(repo, 'services/workpal'), env, stdio:['ignore','pipe','pipe']});

    server.stderr.on('data', data => { logs = (logs + data).slice(-8000); });
    const port = await new Promise((resolve, reject) => {
      let output = '';
      const timer = setTimeout(() => reject(Error('Server startup timed out: ' + logs)), 10000);
      const fail = error => { clearTimeout(timer); reject(error); };
      server.once('error', fail);
      server.once('exit', code => fail(Error('Server exited ' + code + ': ' + logs)));
      server.stdout.on('data', data => {
        output += data;
        const match = output.match(/WORKPAL_READY:(\d+)/);
        if (match) { clearTimeout(timer); resolve(Number(match[1])); }
      });
    });
    const base = 'http://127.0.0.1:' + port;
    browser = await pw.chromium.launch({headless:true});
    const newPage = async (viewport = {width:1440,height:1000}) => {
      const context = await browser.newContext({viewport});
      context.on('page', page => page.on('pageerror', e => errors.push(e.message)));
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === base) return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const page = await context.newPage(); pages.push(page);
      page.on('console', m => diagnostics.push({console:m.type(),text:m.text()}));
      page.on('pageerror', e => diagnostics.push({pageerror:e.message}));
      page.on('response', r => {if(r.status()>=400)diagnostics.push({status:r.status(),url:r.url()});});
      page.on('requestfailed', r => diagnostics.push({failed:r.url(),error:r.failure()}));
      return page;
    };
    await run({base, newPage, runPython, repo, browser, serverEvidence: () => ({pid:server.pid,logs}), expect:pw.expect});
    assert.deepEqual(errors, [], 'browser JavaScript errors');
    assert.deepEqual(external, [], 'external browser requests');
  } catch (error) {
    console.error("FIXTURE DIAGNOSTICS", JSON.stringify(diagnostics), "SERVER", logs);
    for (const page of pages) { try { console.error("PAGE",page.url(),await page.locator("body").innerText({timeout:1000})); } catch (diagnosticError) { console.error("PAGE diagnostic unavailable",diagnosticError.message); } }
    throw error;
  } finally {
    try { await browser?.close(); }
    finally {
      try {
        if (server && server.exitCode === null && server.signalCode === null) {
          await new Promise(resolve => {
            const timer = setTimeout(() => server.kill('SIGKILL'), 3000);
            server.once('exit', () => { clearTimeout(timer); resolve(); });
            server.kill('SIGTERM');
          });
        }
      } finally { await rm(dir, {recursive:true, force:true}); }
    }
  }
}

export async function signIn(page, base, username='owner', password='qa-password') {
  await page.goto(base);
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', {name:'Sign in', exact:true}).click();
}
