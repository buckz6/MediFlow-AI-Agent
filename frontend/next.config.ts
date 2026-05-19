const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://mosaic-duration-dolphin.ngrok-free.dev/api/:path*",
      },
    ];
  },
};

export default nextConfig;