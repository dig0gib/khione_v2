export { default } from "next-auth/middleware";

export const config = {
  // 인증이 필요한 페이지들 지정
  matcher: [
    "/",
    "/settings/:path*",
    "/api/proxy/:path*" // 백엔드 프록시 API도 보호
  ],
};
