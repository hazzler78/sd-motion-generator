/** @type {import('next').NextConfig} */
const nextConfig = {
  // Add Grammarly attributes to the allowed list
  reactStrictMode: true,
  compiler: {
    // Enables the styled-components SWC transform if you're using styled-components
    styledComponents: true
  },
  // Handle Grammarly and other external tool attributes
  experimental: {
    // This will strip data attributes that cause warnings
    optimizeCss: true,
    // Modern webpack features
    webpackBuildWorker: true
  }
}

module.exports = nextConfig 