import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "Khione Terminal Login",
      credentials: {
        username: { label: "ID", type: "text", placeholder: "dig0gib" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        if (
          credentials?.username === process.env.KHIONE_ADMIN_USER &&
          credentials?.password === process.env.KHIONE_ADMIN_PASS
        ) {
          return { id: "1", name: "Administrator", role: "admin" };
        }
        return null;
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = (user as any).role;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).role = token.role;
      }
      return session;
    }
  },
  pages: {
    signIn: "/auth/signin",
  },
  session: {
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24시간 자동 만료
  }
});

export { handler as GET, handler as POST };
