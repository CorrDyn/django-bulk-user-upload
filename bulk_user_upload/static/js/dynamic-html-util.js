const DynamicHTMLUtil = (() => {
  'use strict';

  const htmlToElement = (html) => {
    const template = document.createElement('template');
    html = html.trim();
    template.innerHTML = html;
    return template.content.firstChild;
  };

  return {
    htmlToElement
  };
})();