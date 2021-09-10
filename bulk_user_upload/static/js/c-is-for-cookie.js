// And that's good enough for me.
const cookie = (() => {
  'use strict';
  function setCookie(name,value) {
    document.cookie = `${name}=${value||""}; path=/`;
  }

  function getCookie(name) {
    const cookie = document.cookie.split(';')
      .map(c => c.trim()).filter(c => c.startsWith(`${name}=`));
    return cookie.length ? cookie[0].split("=")[1] : null;
  }

  function eraseCookie(name) {
      document.cookie = `${name}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;`;
  }

  return {
    setCookie,
    getCookie,
    eraseCookie,
  };
})();