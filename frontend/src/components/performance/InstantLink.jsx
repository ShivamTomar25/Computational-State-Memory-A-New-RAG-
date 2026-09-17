import { prefetchRoute, navigateInstant } from "../../performance/prefetch";

export function InstantLink({ to, children, className = "", onClick, ...props }) {
  function prefetch() {
    prefetchRoute(to);
  }

  function handleClick(event) {
    onClick?.(event);

    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    event.preventDefault();
    navigateInstant(to);
  }

  return (
    <a
      href={to}
      className={className}
      onMouseEnter={prefetch}
      onFocus={prefetch}
      onPointerDown={prefetch}
      onClick={handleClick}
      data-instant-link="true"
      {...props}
    >
      {children}
    </a>
  );
}
