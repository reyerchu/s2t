const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/s2t/api',
    createProxyMiddleware({
      target: 'http://localhost:8001',
      changeOrigin: true,
      timeout: 300000, // 5 minutes timeout
      proxyTimeout: 300000, // 5 minutes proxy timeout
      logLevel: 'debug' // Add debug logging
    })
  );
}; 