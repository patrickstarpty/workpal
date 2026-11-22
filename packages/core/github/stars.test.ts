import {expect,it,vi} from 'vitest';
import {fetchGithubStars} from './stars';
it('does not make requests to an unconfigured repository',async()=>{const spy=vi.spyOn(globalThis,'fetch');try{expect(await fetchGithubStars()).toBeNull();expect(spy).not.toHaveBeenCalled();}finally{spy.mockRestore();}});
