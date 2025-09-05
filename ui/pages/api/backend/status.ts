import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

  try {
    const response = await fetch(`${apiBase}/backend/status`);
    
    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    res.status(200).json(data);
  } catch (error) {
    console.error('Backend status error:', error);
    res.status(500).json({ 
      status: 'error',
      error: 'Failed to fetch backend status',
      environment: {
        VVS_FORCE: process.env.VVS_FORCE || '0',
        VVS_ENABLED: process.env.VVS_ENABLED || 'false'
      }
    });
  }
}