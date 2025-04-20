const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/s2t/api',
    createProxyMiddleware({
      target: 'http://localhost:8002',
      changeOrigin: true,
      pathRewrite: {
        '^/s2t/api': '/s2t/api'
      },
      timeout: 300000,
      proxyTimeout: 300000
    })
  );
}; 