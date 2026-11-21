import {launch} from './python-web-dev.mjs';
launch({mode:'production'}).catch(error=>{console.error(error.message);process.exitCode=1;});
