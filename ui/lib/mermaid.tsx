import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

interface MermaidDiagramProps {
  chart: string;
  id?: string;
}

const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ chart, id }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      mermaid.initialize({
        startOnLoad: true,
        theme: 'default',
        securityLevel: 'loose',
        themeVariables: {
          primaryColor: '#6366f1',
          primaryTextColor: '#fff',
          primaryBorderColor: '#4f46e5',
          lineColor: '#e5e7eb',
          secondaryColor: '#f3f4f6',
          tertiaryColor: '#fef3c7',
        },
      });

      const diagramId = id || `mermaid-${Date.now()}`;
      containerRef.current.innerHTML = `<div class="mermaid" id="${diagramId}">${chart}</div>`;
      
      mermaid.contentLoaded();
    }
  }, [chart, id]);

  return (
    <div className="my-4 p-4 bg-gray-50 rounded-lg overflow-x-auto">
      <div ref={containerRef} />
    </div>
  );
};

export default MermaidDiagram;