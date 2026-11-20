import {render} from '@testing-library/react';
import {expect,it} from 'vitest';
import {StarPrompt} from './star-prompt';
it('does not promote an unconfigured public repository',()=>{const {container}=render(<StarPrompt/>);expect(container.textContent).toBe('');});
