import {expect,it,vi} from 'vitest';
import {installLocalLinkNavigation} from './local-link-navigation';
it('lands an editor link at the exact Activity and cleans up',()=>{
 const remove=installLocalLinkNavigation(window);
 window.dispatchEvent(new CustomEvent('workpal:navigate',{detail:{path:'/workpal-team/issues/SMART-4#comment-review'}}));
 expect(location.hash).toBe('#/workpal-team/issues/SMART-4#comment-review');
 remove();
 window.dispatchEvent(new CustomEvent('workpal:navigate',{detail:{path:'/other'}}));
 expect(location.hash).toContain('comment-review');
});
it('keeps modified-click links in a new app tab and rejects external paths',()=>{
 const open=vi.spyOn(window,'open').mockImplementation(()=>null);const remove=installLocalLinkNavigation(window);
 window.dispatchEvent(new CustomEvent('workpal:navigate',{detail:{path:'/workpal-team/issues/SMART-4#comment-review',disposition:'foreground-tab'}}));
 expect(open).toHaveBeenCalledWith(`${location.origin}/#/workpal-team/issues/SMART-4#comment-review`,'_blank','noopener,noreferrer');
 window.dispatchEvent(new CustomEvent('workpal:navigate',{detail:{path:'//external.test',disposition:'foreground-tab'}}));
 expect(open).toHaveBeenCalledTimes(1);remove();open.mockRestore();
});
