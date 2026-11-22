export function reveal(element: HTMLElement | null | undefined) {
  if (!element) return;
  element.focus({preventScroll: true});
  element.scrollIntoView?.({block: 'nearest', behavior: 'auto'});
}
