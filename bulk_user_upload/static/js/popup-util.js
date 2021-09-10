const PopupUtil = (cookie) => {
  'use strict';

  let resizeSubscription = false;
  const recordResize = path => () => {
    cookie.setCookie(
      `size:${path}`,
      JSON.stringify({
        height: window.innerHeight,
        width: window.innerWidth,
      })
    );
  };

  const beginResizeTracking = () => {
    if (resizeSubscription) {
      return;
    } // already subscribed
    if (!resizeSubscription) {
      const { pathname } = new URL(window.location.href);
      window.onresize = recordResize(pathname);
      resizeSubscription = true;
    }
  };

  return {
    beginResizeTracking
  };
};