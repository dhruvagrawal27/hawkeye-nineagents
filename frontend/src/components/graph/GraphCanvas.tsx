import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { GraphResponse } from '@/lib/api';
import { RISK_COLOR } from '@/lib/format';

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: 'Employee' | 'System';
  risk_score: number;
  risk_level: string;
  department: string | null;
  cluster?: number;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  count: number;
}

interface Props {
  data: GraphResponse;
  height?: number;
  highlightId?: string | null;
  showSystems: boolean;
  onSelectNode?: (id: string, label: string) => void;
  clusterByDepartment?: boolean;
}

const DEPT_COLORS: Record<string, string> = {
  'Core Banking': '#60A5FA',
  Treasury: '#34D399',
  Loans: '#FBBF24',
  HRMS: '#F472B6',
  Compliance: '#A78BFA',
};

export function GraphCanvas({
  data,
  height = 540,
  highlightId,
  showSystems,
  onSelectNode,
  clusterByDepartment,
}: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(800);

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      setWidth(entry.contentRect.width);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const { nodes, links } = useMemo(() => {
    const allNodes = data.nodes.map<SimNode>((n) => ({
      id: n.id,
      label: n.label,
      risk_score: n.risk_score,
      risk_level: n.risk_level,
      department: n.department,
    }));
    const allowed = new Set(allNodes.map((n) => n.id));
    const filteredNodes = showSystems ? allNodes : allNodes.filter((n) => n.label === 'Employee');
    const allowedAfter = new Set(filteredNodes.map((n) => n.id));
    const linksOut = data.edges
      .filter((e) => allowed.has(e.source) && allowed.has(e.target) && allowedAfter.has(e.source) && allowedAfter.has(e.target))
      .map<SimLink>((e) => ({ source: e.source, target: e.target, count: e.count || 1 }));
    return { nodes: filteredNodes, links: linksOut };
  }, [data, showSystems]);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const g = svg.append('g');
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on('zoom', (e) => g.attr('transform', e.transform)),
    );

    // Per-department centroids — used when clusterByDepartment is on so
    // same-dept employees actually pull toward each other spatially.
    const DEPT_NAMES = Object.keys(DEPT_COLORS);
    const deptCentroid = (dept: string | null): { x: number; y: number } => {
      const idx = dept ? DEPT_NAMES.indexOf(dept) : -1;
      if (idx < 0) return { x: width / 2, y: height / 2 };
      // Arrange 5 departments in a pentagon around the canvas center.
      const angle = (idx / DEPT_NAMES.length) * Math.PI * 2 - Math.PI / 2;
      const r = Math.min(width, height) * 0.32;
      return { x: width / 2 + Math.cos(angle) * r, y: height / 2 + Math.sin(angle) * r };
    };

    const sim = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(clusterByDepartment ? 50 : 70)
          .strength(clusterByDepartment ? 0.2 : 0.4),
      )
      .force('charge', d3.forceManyBody<SimNode>().strength(clusterByDepartment ? -110 : -180))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(clusterByDepartment ? 0.02 : 0.05))
      .force('collide', d3.forceCollide<SimNode>().radius(20));

    if (clusterByDepartment) {
      sim
        .force(
          'cluster-x',
          d3
            .forceX<SimNode>((d) => (d.label === 'Employee' ? deptCentroid(d.department).x : width / 2))
            .strength(0.18),
        )
        .force(
          'cluster-y',
          d3
            .forceY<SimNode>((d) => (d.label === 'Employee' ? deptCentroid(d.department).y : height / 2))
            .strength(0.18),
        );
    }

    // Department labels at each centroid (only when clustering is on)
    if (clusterByDepartment) {
      const labels = g.append('g').attr('class', 'dept-labels');
      DEPT_NAMES.forEach((dept) => {
        const { x, y } = deptCentroid(dept);
        const color = DEPT_COLORS[dept];
        labels
          .append('circle')
          .attr('cx', x).attr('cy', y).attr('r', 60)
          .attr('fill', color).attr('fill-opacity', 0.04)
          .attr('stroke', color).attr('stroke-opacity', 0.25)
          .attr('stroke-dasharray', '3 3');
        labels
          .append('text')
          .attr('x', x).attr('y', y - 70)
          .attr('text-anchor', 'middle')
          .attr('fill', color)
          .attr('opacity', 0.7)
          .attr('font-family', 'JetBrains Mono, monospace')
          .attr('font-size', 10)
          .attr('letter-spacing', '0.2em')
          .text(dept.toUpperCase());
      });
    }

    const link = g
      .append('g')
      .attr('stroke', '#334155')
      .attr('stroke-opacity', 0.5)
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke-width', (d) => Math.max(0.5, Math.min(4, Math.sqrt(d.count))));

    const node = g
      .append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3
          .drag<SVGGElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      )
      .on('click', (_event, d) => onSelectNode?.(d.id, d.label));

    node
      .append('circle')
      .attr('r', (d) => (d.label === 'Employee' ? 6 + d.risk_score * 12 : 5))
      .attr('fill', (d) => {
        if (d.label === 'System') return '#334155';
        if (clusterByDepartment && d.department && DEPT_COLORS[d.department]) {
          return DEPT_COLORS[d.department];
        }
        return RISK_COLOR[d.risk_level] ?? '#64748b';
      })
      .attr('stroke', (d) => (d.id === highlightId ? '#3B82F6' : '#0B1020'))
      .attr('stroke-width', (d) => (d.id === highlightId ? 3 : 1.5));

    node
      .filter((d) => d.label === 'Employee' && d.risk_score > 0.16)
      .append('circle')
      .attr('r', (d) => 6 + d.risk_score * 12 + 4)
      .attr('fill', 'none')
      .attr('stroke', (d) => RISK_COLOR[d.risk_level] ?? '#64748b')
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', 1.5);

    node
      .append('text')
      .text((d) => d.id.slice(-6))
      .attr('x', 10)
      .attr('y', 3)
      .attr('font-size', 10)
      .attr('fill', '#94a3b8')
      .attr('font-family', 'JetBrains Mono, monospace')
      .style('pointer-events', 'none');

    sim.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0);
      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      sim.stop();
    };
  }, [nodes, links, width, height, highlightId, clusterByDepartment, onSelectNode]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full"
        style={{ background: 'radial-gradient(circle at center, #0F172A 0%, #0B1020 70%)' }}
      />
    </div>
  );
}
