import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    
    let backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8001";
    if (backendUrl.endsWith("/")) {
      backendUrl = backendUrl.slice(0, -1);
    }
    
    console.log(`Proxying request to: ${backendUrl}/chat`);
    
    const response = await fetch(`${backendUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      console.error(`Backend returned ${response.status}: ${response.statusText}`);
      const text = await response.text();
      console.error(`Backend error body: ${text}`);
      return NextResponse.json({ error: "Backend error", details: text }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Proxy error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
