import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { ConfidencePoint } from '../types';

interface Props {
  timeline: ConfidencePoint[];
  participantNames: Record<string, string>;
}

const COLORS = [
  '#6366f1',
  '#ec4899',
  '#8b5cf6',
  '#f59e0b',
  '#22c55e',
  '#3b82f6',
  '#ef4444',
];

export const ConfidenceGraph: React.FC<Props> = ({ timeline, participantNames }) => {
  const chartData = useMemo(() => {
    if (timeline.length === 0) return [];

    // Pre-downsample raw timeline list if it grows large to limit group-by computations
    let sampledTimeline = timeline;
    if (timeline.length > 200) {
      const filterStep = Math.ceil(timeline.length / 100);
      sampledTimeline = timeline.filter((_, i) => i % filterStep === 0 || i === timeline.length - 1);
    }

    // Group by timestamp
    const byTime: Record<number, Record<string, number>> = {};
    const participants = new Set<string>();

    for (const point of sampledTimeline) {
      const t = Math.round(point.timestamp);
      if (!byTime[t]) byTime[t] = {};
      byTime[t][point.participant_id] = Math.round(point.confidence * 100);
      participants.add(point.participant_id);
    }

    // Convert to chart data array
    const times = Object.keys(byTime).map(Number).sort((a, b) => a - b);

    // Downsample if too many points
    const step = Math.max(1, Math.floor(times.length / 60));
    const sampledTimes = times.filter((_, i) => i % step === 0 || i === times.length - 1);

    return sampledTimes.map(t => {
      const row: Record<string, number | string> = { time: t };
      for (const pid of participants) {
        row[pid] = byTime[t]?.[pid] ?? 0;
      }
      return row;
    });
  }, [timeline]);

  const participantIds = useMemo(() => {
    const ids = new Set<string>();
    timeline.forEach(p => ids.add(p.participant_id));
    return Array.from(ids);
  }, [timeline]);

  if (chartData.length < 2) {
    return (
      <div>
        <div className="section-title">Confidence Over Time</div>
        <div className="chart-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
            Collecting data points...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="section-title">Confidence Over Time</div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="time"
              tick={{ fill: '#64748b', fontSize: 10 }}
              tickFormatter={(v: number) => `${v}s`}
              stroke="rgba(255,255,255,0.06)"
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: '#64748b', fontSize: 10 }}
              tickFormatter={(v: number) => `${v}%`}
              stroke="rgba(255,255,255,0.06)"
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(17, 24, 39, 0.95)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8,
                fontSize: 12,
                color: '#f1f5f9',
              }}
              formatter={(value: number, name: string) => [`${value}%`, participantNames[name] || name]}
              labelFormatter={(label: number) => `Time: ${label}s`}
            />
            <Legend
              formatter={(value: string) => (
                <span style={{ color: '#94a3b8', fontSize: 11 }}>
                  {participantNames[value] || value}
                </span>
              )}
            />
            {participantIds.map((pid, i) => (
              <Line
                key={pid}
                type="monotone"
                dataKey={pid}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
