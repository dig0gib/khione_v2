"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SignInPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await signIn("credentials", {
      username,
      password,
      redirect: false,
    });

    if (result?.error) {
      setError("아이디 또는 비밀번호가 올바르지 않습니다.");
    } else {
      router.push("/");
      router.refresh();
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>❄️ Khione Terminal</h1>
        <p>전략 트레이딩 시스템 접근 인증</p>
        
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button type="submit">Login</button>
        </form>
        
        {error && <p className="error-msg">{error}</p>}
      </div>

      <style jsx>{`
        .login-container {
          display: flex;
          justify-content: center;
          align-items: center;
          height: 100vh;
          background: #0f172a;
          color: white;
          font-family: 'Inter', sans-serif;
        }
        .login-box {
          background: #1e293b;
          padding: 2.5rem;
          border-radius: 1rem;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          width: 100%;
          max-width: 400px;
          text-align: center;
        }
        h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        p { color: #94a3b8; margin-bottom: 2rem; }
        input {
          width: 100%;
          padding: 0.8rem;
          margin-bottom: 1rem;
          border-radius: 0.5rem;
          border: 1px solid #334155;
          background: #0f172a;
          color: white;
          outline: none;
        }
        button {
          width: 100%;
          padding: 0.8rem;
          background: #3b82f6;
          color: white;
          border: none;
          border-radius: 0.5rem;
          cursor: pointer;
          font-weight: 600;
          transition: background 0.2s;
        }
        button:hover { background: #2563eb; }
        .error-msg { color: #f87171; margin-top: 1rem; font-size: 0.9rem; }
      `}</style>
    </div>
  );
}
