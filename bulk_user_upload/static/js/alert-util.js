const AlertUtil = (() => {
  'use strict';

  const $ = django.jQuery;

  const severity_levels = {
    DEBUG: 'debug',
    INFO: 'info',
    SUCCESS: 'success',
    WARNING: 'warning',
    ERROR: 'error',
  };

  const create_alert_message = (message, { severity = severity_levels.INFO, id = 'message' } ) => {
    const container = document.createElement('ul');
    container.id = id;
    container.className = "messagelist";
    const messageNode = document.createElement('li');
    messageNode.className = severity;
    messageNode.appendChild(document.createTextNode(message));
    container.appendChild(messageNode);

    return {
      node: container,
      severity,
      show: () => $(container).show(),
      hide: () => $(container).hide(),
    };
  };

  return {
    create_alert_message,
    severity: severity_levels
  };
})();