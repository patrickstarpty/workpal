import {render} from '@testing-library/react';
import {expect,it} from 'vitest';
import {HelpLauncher} from './help-launcher';
it('does not expose unconfigured external brand services',()=>{const {container}=render(<HelpLauncher/>);expect(container.querySelector('a')).toBeNull();});
