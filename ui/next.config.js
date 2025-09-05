/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/chat/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/chat/:path*`,
      },
    ]
  },
}

module.exports = nextConfig