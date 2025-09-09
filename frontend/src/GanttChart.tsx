import React, { useCallback, useEffect, useMemo, useState } from 'react';

interface Schedule {
    id: number;
    name: string;
    total_activities: number;
    proj_short_name?: string;
}

interface Activity {
    task_id: string;
    task_name: string;
    wbs_id: string;
    duration_days: number;
    early_start_date: string | null;
    early_end_date: string | null;
    actual_start_date: string | null;
    actual_end_date: string | null;
    progress_pct: number;
    total_float_days: number;
    task_type: string;
    status_code: string;
    hierarchy_path: string;
}

interface WBSItem {
    wbs_id: string;
    wbs_name: string;
    parent_wbs_id: string | null;
    level: number;
    full_path: string;
}

interface GanttNode {
    id: string;
    type: 'wbs' | 'activity';
    name: string;
    level: number;
    isExpanded: boolean;
    planned_start: Date | null;
    planned_end: Date | null;
    actual_start: Date | null;
    actual_end: Date | null;
    progress: number;
    duration: number;
    float: number;
    isCritical: boolean;
    color: string;
    task_id?: string;
    wbs_code?: string;
    activityCount?: number;
}

interface GanttChartProps {
    schedule: Schedule;
    onBackToSchedules: () => void;
}

const GanttChart: React.FC<GanttChartProps> = ({ schedule, onBackToSchedules }) => {
    const [activities, setActivities] = useState<Activity[]>([]);
    const [wbsStructure, setWbsStructure] = useState<WBSItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedWBS, setExpandedWBS] = useState<Set<string>>(new Set());
    const [viewMode, setViewMode] = useState<'months' | 'weeks' | 'days'>('months');
    const [showCriticalPath, setShowCriticalPath] = useState(true);
    const [dateMode, setDateMode] = useState<'planned' | 'actual' | 'both'>('planned');

    // ✅ FIXED: Scroll state management
    const [scrollLeft, setScrollLeft] = useState(0);
    const [scrollTop, setScrollTop] = useState(0);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                setError(null);

                const response = await fetch(`http://localhost:5000/api/schedules/${schedule.id}/activities?per_page=5000`);
                if (!response.ok) throw new Error(`Failed to load activities: ${response.status}`);

                const data = await response.json();
                if (data.success) {
                    setActivities(data.activities || []);
                    setWbsStructure(data.wbs_structure || []);

                    const rootWBS = data.wbs_structure
                        ?.filter((wbs: WBSItem) => wbs.level <= 1)
                        ?.map((wbs: WBSItem) => wbs.wbs_id) || [];
                    setExpandedWBS(new Set(['project-root', ...rootWBS.slice(0, 3)]));
                } else {
                    throw new Error(data.error || 'Failed to load activities');
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load data');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [schedule.id]);

    // ✅ FIXED: Project timeline calculation
    const projectTimeline = useMemo(() => {
        if (activities.length === 0) return null;

        const validActivities = activities.filter(a => a.early_start_date && a.early_end_date);
        if (validActivities.length === 0) return null;

        const startDates = validActivities.map(a => new Date(a.early_start_date!));
        const endDates = validActivities.map(a => new Date(a.early_end_date!));

        const projectStart = new Date(Math.min(...startDates.map(d => d.getTime())));
        const projectEnd = new Date(Math.max(...endDates.map(d => d.getTime())));

        // Add 30 days padding
        const padDays = 30;
        const timelineStart = new Date(projectStart.getTime() - (padDays * 24 * 60 * 60 * 1000));
        const timelineEnd = new Date(projectEnd.getTime() + (padDays * 24 * 60 * 60 * 1000));

        return {
            start: timelineStart,
            end: timelineEnd,
            projectStart,
            projectEnd,
            totalDays: Math.ceil((timelineEnd.getTime() - timelineStart.getTime()) / (24 * 60 * 60 * 1000))
        };
    }, [activities]);

    // Generate timeline columns
    const timelineColumns = useMemo(() => {
        if (!projectTimeline) return [];
        const columns = [];
        const current = new Date(projectTimeline.start);
        const end = projectTimeline.end;

        while (current <= end) {
            if (viewMode === 'months') {
                columns.push({
                    date: new Date(current),
                    label: current.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }),
                    isStart: current.getDate() === 1
                });
                current.setMonth(current.getMonth() + 1);
            } else if (viewMode === 'weeks') {
                columns.push({
                    date: new Date(current),
                    label: `W${Math.ceil(current.getDate() / 7)}`,
                    isStart: current.getDay() === 1
                });
                current.setDate(current.getDate() + 7);
            } else {
                columns.push({
                    date: new Date(current),
                    label: current.getDate().toString(),
                    isStart: true
                });
                current.setDate(current.getDate() + 1);
            }
        }
        return columns;
    }, [projectTimeline, viewMode]);

    // ✅ FIXED: Build Gantt data with proper WBS rollups
    const ganttData = useMemo(() => {
        const nodes: GanttNode[] = [];
        if (!projectTimeline || wbsStructure.length === 0) return nodes;

        const activitiesByWBS = new Map<string, Activity[]>();
        activities.forEach(activity => {
            const wbsId = activity.wbs_id;
            if (!activitiesByWBS.has(wbsId)) {
                activitiesByWBS.set(wbsId, []);
            }
            activitiesByWBS.get(wbsId)!.push(activity);
        });

        const buildWBSNodes = (parentId: string | null, level: number) => {
            const childWBS = wbsStructure
                .filter(wbs => {
                    if (parentId === null) return wbs.level === 0 || !wbs.parent_wbs_id;
                    return wbs.parent_wbs_id === parentId;
                })
                .sort((a, b) => a.wbs_name.localeCompare(b.wbs_name));

            childWBS.forEach(wbs => {
                const wbsActivities = activitiesByWBS.get(wbs.wbs_id) || [];
                const isExpanded = expandedWBS.has(wbs.wbs_id);

                // ✅ FIXED: Calculate WBS summary properly
                let wbsStart = null;
                let wbsEnd = null;
                let totalDuration = 0;
                let weightedProgress = 0;

                if (wbsActivities.length > 0) {
                    const validActivities = wbsActivities.filter(a => a.early_start_date && a.early_end_date);
                    if (validActivities.length > 0) {
                        const startDates = validActivities.map(a => new Date(a.early_start_date!));
                        const endDates = validActivities.map(a => new Date(a.early_end_date!));
                        wbsStart = new Date(Math.min(...startDates.map(d => d.getTime())));
                        wbsEnd = new Date(Math.max(...endDates.map(d => d.getTime())));

                        totalDuration = wbsActivities.reduce((sum, a) => sum + (a.duration_days || 0), 0);
                        weightedProgress = totalDuration > 0 ?
                            wbsActivities.reduce((sum, a) => sum + ((a.progress_pct || 0) * (a.duration_days || 0)), 0) / totalDuration : 0;
                    }
                }

                const wbsNode: GanttNode = {
                    id: `wbs-${wbs.wbs_id}`,
                    type: 'wbs',
                    name: wbs.wbs_name,
                    level: level,
                    isExpanded: isExpanded,
                    planned_start: wbsStart,
                    planned_end: wbsEnd,
                    actual_start: null,
                    actual_end: null,
                    progress: Math.round(weightedProgress),
                    duration: totalDuration, // ✅ FIXED: Proper duration calculation
                    float: 0,
                    isCritical: false,
                    color: `hsl(${(level * 60) % 360}, 60%, 70%)`,
                    wbs_code: wbs.wbs_id,
                    activityCount: wbsActivities.length
                };

                nodes.push(wbsNode);

                if (isExpanded) {
                    wbsActivities
                        .sort((a, b) => {
                            const dateA = a.early_start_date ? new Date(a.early_start_date).getTime() : 0;
                            const dateB = b.early_start_date ? new Date(b.early_start_date).getTime() : 0;
                            return dateA - dateB;
                        })
                        .forEach(activity => {
                            const isCritical = (activity.total_float_days || 0) === 0;

                            nodes.push({
                                id: `activity-${activity.task_id}`,
                                type: 'activity',
                                name: activity.task_name,
                                level: level + 1,
                                isExpanded: false,
                                planned_start: activity.early_start_date ? new Date(activity.early_start_date) : null,
                                planned_end: activity.early_end_date ? new Date(activity.early_end_date) : null,
                                actual_start: activity.actual_start_date ? new Date(activity.actual_start_date) : null,
                                actual_end: activity.actual_end_date ? new Date(activity.actual_end_date) : null,
                                progress: activity.progress_pct || 0,
                                duration: activity.duration_days || 0, // ✅ FIXED: Use actual duration_days
                                float: activity.total_float_days || 0,
                                isCritical: isCritical,
                                color: isCritical ? '#FF5722' :
                                    activity.progress_pct >= 100 ? '#4CAF50' :
                                        activity.progress_pct > 0 ? '#2196F3' : '#9E9E9E',
                                task_id: activity.task_id,
                                wbs_code: activity.wbs_id
                            });
                        });

                    buildWBSNodes(wbs.wbs_id, level + 1);
                }
            });
        };

        buildWBSNodes(null, 0);
        return nodes;
    }, [wbsStructure, activities, expandedWBS, projectTimeline]);

    // ✅ FIXED: Calculate bar style with correct positioning
    const calculateBarStyle = useCallback((node: GanttNode, barType: 'planned' | 'actual' = 'planned') => {
        if (!projectTimeline) return { display: 'none' };

        let startDate = barType === 'planned' ? node.planned_start : node.actual_start;
        let endDate = barType === 'planned' ? node.planned_end : node.actual_end;

        if (!startDate || !endDate) return { display: 'none' };

        const totalDays = projectTimeline.totalDays;
        const startOffset = (startDate.getTime() - projectTimeline.start.getTime()) / (24 * 60 * 60 * 1000);
        const duration = (endDate.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000);

        const leftPercent = (startOffset / totalDays) * 100;
        const widthPercent = Math.max((duration / totalDays) * 100, 0.5);

        return {
            left: `${leftPercent}%`,
            width: `${widthPercent}%`,
            backgroundColor: node.color,
            opacity: showCriticalPath ? (node.isCritical ? 1 : 0.7) : 1
        };
    }, [projectTimeline, showCriticalPath]);

    const toggleWBS = (wbsId: string) => {
        const newExpanded = new Set(expandedWBS);
        if (newExpanded.has(wbsId)) {
            newExpanded.delete(wbsId);
        } else {
            newExpanded.add(wbsId);
        }
        setExpandedWBS(newExpanded);
    };

    // ✅ FIXED: Proper scroll handlers
    const handleTaskListScroll = (e: React.UIEvent<HTMLDivElement>) => {
        const newScrollTop = e.currentTarget.scrollTop;
        setScrollTop(newScrollTop);

        // Sync timeline vertical scroll
        const timelineBody = document.getElementById('timeline-body');
        if (timelineBody && timelineBody.scrollTop !== newScrollTop) {
            timelineBody.scrollTop = newScrollTop;
        }
    };

    const handleTimelineScroll = (e: React.UIEvent<HTMLDivElement>) => {
        const newScrollLeft = e.currentTarget.scrollLeft;
        const newScrollTop = e.currentTarget.scrollTop;

        setScrollLeft(newScrollLeft);
        setScrollTop(newScrollTop);

        // Sync header horizontal scroll
        const header = document.getElementById('timeline-header');
        if (header && header.scrollLeft !== newScrollLeft) {
            header.scrollLeft = newScrollLeft;
        }

        // Sync task list vertical scroll
        const taskList = document.getElementById('task-list-body');
        if (taskList && taskList.scrollTop !== newScrollTop) {
            taskList.scrollTop = newScrollTop;
        }
    };

    if (loading) {
        return (
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100vh',
                fontSize: '18px',
                color: '#666',
                flexDirection: 'column',
                gap: '15px'
            }}>
                <div>⏳ Loading Gantt chart data...</div>
                <div style={{ fontSize: '14px' }}>
                    {schedule.total_activities?.toLocaleString()} activities
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{
                padding: '40px',
                textAlign: 'center',
                color: '#dc3545',
                backgroundColor: '#fff',
                margin: '20px',
                borderRadius: '8px'
            }}>
                <h3>⚠️ Error Loading Gantt Data</h3>
                <p>{error}</p>
                <button onClick={onBackToSchedules}>← Back to Schedules</button>
            </div>
        );
    }

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#f5f5f5',
            overflow: 'hidden'
        }}>
            {/* Header */}
            <div style={{
                backgroundColor: 'white',
                padding: '16px 24px',
                borderBottom: '1px solid #e0e0e0',
                boxShadow: '0 2px 4px rgba(0,0,0,0.08)'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div>
                        <h2 style={{ margin: '0 0 8px 0', color: '#1a1a1a', fontSize: '20px' }}>
                            📊 Gantt Chart - {schedule.proj_short_name || schedule.name}
                        </h2>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                            {ganttData.filter(n => n.type === 'activity').length} activities displayed
                        </div>
                    </div>
                    <button onClick={onBackToSchedules} style={{
                        padding: '8px 16px',
                        backgroundColor: '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px'
                    }}>
                        ← Back to Schedules
                    </button>
                </div>

                {/* Controls */}
                <div style={{
                    display: 'flex',
                    gap: '16px',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    paddingTop: '8px',
                    borderTop: '1px solid #f0f0f0'
                }}>
                    {/* Date Mode Toggle */}
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        <label style={{ fontSize: '12px', fontWeight: '600', color: '#333', marginRight: '8px' }}>
                            View:
                        </label>
                        <button
                            onClick={() => setDateMode('planned')}
                            style={{
                                padding: '6px 12px',
                                backgroundColor: dateMode === 'planned' ? '#2196F3' : '#f5f5f5',
                                color: dateMode === 'planned' ? 'white' : '#666',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '11px',
                                fontWeight: '500'
                            }}
                        >
                            📅 Planned
                        </button>
                        <button
                            onClick={() => setDateMode('actual')}
                            style={{
                                padding: '6px 12px',
                                backgroundColor: dateMode === 'actual' ? '#4CAF50' : '#f5f5f5',
                                color: dateMode === 'actual' ? 'white' : '#666',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '11px',
                                fontWeight: '500'
                            }}
                        >
                            ✅ Actual
                        </button>
                        <button
                            onClick={() => setDateMode('both')}
                            style={{
                                padding: '6px 12px',
                                backgroundColor: dateMode === 'both' ? '#FF9800' : '#f5f5f5',
                                color: dateMode === 'both' ? 'white' : '#666',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '11px',
                                fontWeight: '500'
                            }}
                        >
                            📊 Both
                        </button>
                    </div>

                    <select
                        value={viewMode}
                        onChange={(e) => setViewMode(e.target.value as 'months' | 'weeks' | 'days')}
                        style={{
                            padding: '6px 12px',
                            border: '1px solid #ddd',
                            borderRadius: '4px',
                            fontSize: '11px'
                        }}
                    >
                        <option value="months">Monthly</option>
                        <option value="weeks">Weekly</option>
                        <option value="days">Daily</option>
                    </select>

                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
                        <input
                            type="checkbox"
                            checked={showCriticalPath}
                            onChange={(e) => setShowCriticalPath(e.target.checked)}
                        />
                        Highlight Critical Path
                    </label>
                </div>
            </div>

            {/* Main Gantt Area */}
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                {/* ✅ ENHANCED: Left Panel - P6 Style Columns */}
                <div style={{
                    width: '600px', // ✅ INCREASED: More space for all columns
                    backgroundColor: 'white',
                    borderRight: '1px solid #e0e0e0',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden'
                }}>
                    {/* ✅ ENHANCED: P6 Style Headers */}
                    <div style={{
                        padding: '8px 16px',
                        backgroundColor: '#f8f9fa',
                        borderBottom: '1px solid #e0e0e0',
                        fontSize: '10px',
                        fontWeight: '700',
                        color: '#495057',
                        textTransform: 'uppercase',
                        display: 'grid',
                        gridTemplateColumns: '80px 80px 220px 60px 60px', // ✅ PRIMAVERA P6 LAYOUT
                        gap: '8px',
                        alignItems: 'center'
                    }}>
                        <div>ACTIVITY ID</div>
                        <div>WBS</div>
                        <div>ACTIVITY NAME</div>
                        <div>DURATION</div>
                        <div>% COMPL</div>
                    </div>

                    {/* ✅ FIXED: Task List with Proper Alignment */}
                    <div
                        id="task-list-body"
                        style={{
                            flex: 1,
                            overflowY: 'auto',
                            overflowX: 'hidden'
                        }}
                        onScroll={handleTaskListScroll}
                    >
                        {ganttData.map((node, index) => (
                            <div
                                key={node.id}
                                style={{
                                    padding: '6px 16px',
                                    borderBottom: '1px solid #f0f0f0',
                                    backgroundColor: index % 2 === 0 ? '#fafbfc' : 'white',
                                    cursor: node.type === 'wbs' ? 'pointer' : 'default',
                                    display: 'grid',
                                    gridTemplateColumns: '80px 80px 220px 60px 60px',
                                    gap: '8px',
                                    alignItems: 'center',
                                    fontSize: '11px',
                                    minHeight: '32px' // ✅ FIXED: Consistent row height
                                }}
                                onClick={() => {
                                    if (node.type === 'wbs') {
                                        toggleWBS(node.id.replace('wbs-', ''));
                                    }
                                }}
                            >
                                {/* Activity ID */}
                                <div style={{
                                    fontSize: '10px',
                                    fontFamily: 'monospace',
                                    color: node.type === 'wbs' ? '#1976d2' : '#333',
                                    fontWeight: node.type === 'wbs' ? '600' : '400',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis'
                                }}>
                                    {node.type === 'wbs' ? 'WBS' : node.task_id}
                                </div>

                                {/* WBS Code */}
                                <div style={{
                                    fontSize: '10px',
                                    fontFamily: 'monospace',
                                    color: '#666',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis'
                                }}>
                                    {node.wbs_code || '-'}
                                </div>

                                {/* ✅ ENHANCED: Activity Name with Hierarchy */}
                                <div style={{
                                    paddingLeft: `${node.level * 12}px`,
                                    minWidth: 0,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px'
                                }}>
                                    {node.type === 'wbs' && (
                                        <span style={{ fontSize: '8px', color: '#666', flexShrink: 0 }}>
                                            {node.isExpanded ? '▼' : '▶'}
                                        </span>
                                    )}

                                    <span style={{
                                        fontSize: '11px',
                                        fontWeight: node.type === 'wbs' ? '600' : '400',
                                        color: node.type === 'wbs' ? '#1976d2' :
                                            node.isCritical ? '#f44336' : '#333',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap'
                                    }}>
                                        {node.name}
                                    </span>

                                    {node.isCritical && (
                                        <span style={{
                                            fontSize: '7px',
                                            backgroundColor: '#ffebee',
                                            color: '#f44336',
                                            padding: '1px 2px',
                                            borderRadius: '2px',
                                            fontWeight: '700',
                                            flexShrink: 0
                                        }}>
                                            CRIT
                                        </span>
                                    )}
                                </div>

                                {/* ✅ FIXED: Duration */}
                                <div style={{
                                    textAlign: 'center',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    color: '#333'
                                }}>
                                    {node.duration > 0 ? `${Math.round(node.duration)}d` : '-'}
                                </div>

                                {/* ✅ NEW: % Complete */}
                                <div style={{
                                    textAlign: 'center',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    color: node.progress >= 100 ? '#4CAF50' :
                                        node.progress > 0 ? '#2196F3' : '#666'
                                }}>
                                    {Math.round(node.progress)}%
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Right Panel - Timeline */}
                <div style={{
                    flex: 1,
                    backgroundColor: 'white',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden'
                }}>
                    {/* Timeline Header */}
                    <div
                        id="timeline-header"
                        style={{
                            height: '32px',
                            backgroundColor: '#f8f9fa',
                            borderBottom: '1px solid #e0e0e0',
                            position: 'relative',
                            overflowX: 'hidden'
                        }}
                    >
                        <div style={{
                            height: '100%',
                            minWidth: `${Math.max(timelineColumns.length * 60, 800)}px`,
                            display: 'flex',
                            transform: `translateX(-${scrollLeft}px)` // ✅ FIXED: Manual sync
                        }}>
                            {timelineColumns.map((col, index) => (
                                <div
                                    key={index}
                                    style={{
                                        flex: 1,
                                        minWidth: '60px',
                                        padding: '6px 2px',
                                        borderRight: '1px solid #e0e0e0',
                                        fontSize: '9px',
                                        fontWeight: '600',
                                        color: '#495057',
                                        textAlign: 'center'
                                    }}
                                >
                                    {col.label}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* ✅ FIXED: Timeline Body */}
                    <div
                        id="timeline-body"
                        style={{
                            flex: 1,
                            position: 'relative',
                            overflowX: 'auto',
                            overflowY: 'auto'
                        }}
                        onScroll={handleTimelineScroll}
                    >
                        <div style={{
                            minWidth: `${Math.max(timelineColumns.length * 60, 800)}px`,
                            height: `${ganttData.length * 32}px`, // ✅ FIXED: Match row height
                            position: 'relative'
                        }}>
                            {/* Grid Lines */}
                            {timelineColumns.map((_, index) => (
                                <div
                                    key={`grid-${index}`}
                                    style={{
                                        position: 'absolute',
                                        left: `${(index / timelineColumns.length) * 100}%`,
                                        top: 0,
                                        bottom: 0,
                                        width: '1px',
                                        backgroundColor: '#e9ecef',
                                        zIndex: 1
                                    }}
                                />
                            ))}

                            {/* Gantt Bars */}
                            {ganttData.map((node, rowIndex) => (
                                <div
                                    key={`row-${node.id}`}
                                    style={{
                                        position: 'absolute',
                                        top: `${rowIndex * 32}px`, // ✅ FIXED: Match row height
                                        left: 0,
                                        right: 0,
                                        height: '32px',
                                        backgroundColor: rowIndex % 2 === 0 ? '#fafbfc' : 'white',
                                        borderBottom: '1px solid #f0f0f0',
                                        zIndex: 2
                                    }}
                                >
                                    {/* Bar Rendering */}
                                    {dateMode === 'planned' && (
                                        <div
                                            style={{
                                                position: 'absolute',
                                                top: '6px',
                                                height: '20px',
                                                borderRadius: '3px',
                                                zIndex: 3,
                                                border: node.isCritical ? '2px solid #f44336' : '1px solid rgba(0,0,0,0.1)',
                                                ...calculateBarStyle(node, 'planned')
                                            }}
                                        >
                                            {/* Progress Bar */}
                                            {node.progress > 0 && (
                                                <div style={{
                                                    position: 'absolute',
                                                    left: 0,
                                                    top: 0,
                                                    bottom: 0,
                                                    width: `${node.progress}%`,
                                                    backgroundColor: '#4CAF50',
                                                    borderRadius: '2px',
                                                    opacity: 0.8
                                                }} />
                                            )}

                                            {/* ✅ PRIMAVERA STYLE: Activity Name at End of Bar */}
                                            {node.type === 'activity' && (
                                                <div style={{
                                                    position: 'absolute',
                                                    right: '-4px',
                                                    top: '50%',
                                                    transform: 'translateY(-50%)',
                                                    fontSize: '9px',
                                                    color: '#333',
                                                    fontWeight: '500',
                                                    whiteSpace: 'nowrap',
                                                    backgroundColor: 'rgba(255,255,255,0.9)',
                                                    padding: '1px 3px',
                                                    borderRadius: '2px',
                                                    border: '1px solid #ddd',
                                                    maxWidth: '200px',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis'
                                                }}>
                                                    {node.name}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {dateMode === 'actual' && (
                                        <div
                                            style={{
                                                position: 'absolute',
                                                top: '6px',
                                                height: '20px',
                                                borderRadius: '3px',
                                                zIndex: 3,
                                                border: '1px solid rgba(0,0,0,0.1)',
                                                backgroundColor: '#4CAF50',
                                                opacity: 0.9,
                                                ...calculateBarStyle(node, 'actual')
                                            }}
                                        >
                                            {/* Activity Name at End */}
                                            {node.type === 'activity' && (
                                                <div style={{
                                                    position: 'absolute',
                                                    right: '-4px',
                                                    top: '50%',
                                                    transform: 'translateY(-50%)',
                                                    fontSize: '9px',
                                                    color: '#333',
                                                    fontWeight: '500',
                                                    whiteSpace: 'nowrap',
                                                    backgroundColor: 'rgba(255,255,255,0.9)',
                                                    padding: '1px 3px',
                                                    borderRadius: '2px',
                                                    border: '1px solid #ddd'
                                                }}>
                                                    {node.name}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {dateMode === 'both' && (
                                        <>
                                            {/* Planned Bar (Top) */}
                                            <div
                                                style={{
                                                    position: 'absolute',
                                                    top: '4px',
                                                    height: '10px',
                                                    borderRadius: '2px',
                                                    zIndex: 3,
                                                    border: node.isCritical ? '1px solid #f44336' : '1px solid rgba(0,0,0,0.1)',
                                                    opacity: 0.8,
                                                    ...calculateBarStyle(node, 'planned')
                                                }}
                                            >
                                                {/* Progress */}
                                                {node.progress > 0 && (
                                                    <div style={{
                                                        position: 'absolute',
                                                        left: 0,
                                                        top: 0,
                                                        bottom: 0,
                                                        width: `${node.progress}%`,
                                                        backgroundColor: '#2196F3',
                                                        borderRadius: '1px',
                                                        opacity: 0.9
                                                    }} />
                                                )}
                                            </div>

                                            {/* Actual Bar (Bottom) */}
                                            <div
                                                style={{
                                                    position: 'absolute',
                                                    top: '18px',
                                                    height: '10px',
                                                    borderRadius: '2px',
                                                    zIndex: 4,
                                                    border: '1px solid rgba(0,0,0,0.1)',
                                                    backgroundColor: '#4CAF50',
                                                    opacity: 0.9,
                                                    ...calculateBarStyle(node, 'actual')
                                                }}
                                            />

                                            {/* Activity Name */}
                                            {node.type === 'activity' && (
                                                <div style={{
                                                    position: 'absolute',
                                                    right: '-4px',
                                                    top: '50%',
                                                    transform: 'translateY(-50%)',
                                                    fontSize: '9px',
                                                    color: '#333',
                                                    fontWeight: '500',
                                                    whiteSpace: 'nowrap',
                                                    backgroundColor: 'rgba(255,255,255,0.9)',
                                                    padding: '1px 3px',
                                                    borderRadius: '2px',
                                                    border: '1px solid #ddd'
                                                }}>
                                                    {node.name}
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            ))}

                            {/* ✅ FIXED: Today Line - Correct Position */}
                            {projectTimeline && (() => {
                                const today = new Date();
                                const todayOffset = (today.getTime() - projectTimeline.start.getTime()) / (24 * 60 * 60 * 1000);
                                const todayPercent = (todayOffset / projectTimeline.totalDays) * 100;

                                // Only show if today is within timeline bounds (0% to 100%)
                                return todayPercent >= 0 && todayPercent <= 100;
                            })() && (
                                    <div
                                        style={{
                                            position: 'absolute',
                                            left: `${((new Date().getTime() - projectTimeline.start.getTime()) / (24 * 60 * 60 * 1000) / projectTimeline.totalDays) * 100}%`,
                                            top: 0,
                                            bottom: 0,
                                            width: '2px',
                                            background: 'repeating-linear-gradient(to bottom, #999999 0px, #999999 4px, transparent 4px, transparent 8px)',
                                            zIndex: 10
                                        }}
                                    >
                                        <div style={{
                                            position: 'absolute',
                                            top: '-18px',
                                            left: '50%',
                                            transform: 'translateX(-50%)',
                                            backgroundColor: '#999999',
                                            color: 'white',
                                            padding: '1px 4px',
                                            fontSize: '8px',
                                            borderRadius: '2px',
                                            whiteSpace: 'nowrap'
                                        }}>
                                            Today
                                        </div>
                                    </div>
                                )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Status Bar */}
            <div style={{
                backgroundColor: '#f8f9fa',
                padding: '6px 24px',
                borderTop: '1px solid #e0e0e0',
                fontSize: '10px',
                color: '#666',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
            }}>
                <div>
                    Gantt View • {ganttData.filter(n => n.type === 'activity').length} activities •
                    {ganttData.filter(n => n.isCritical).length} critical •
                    View: {dateMode === 'planned' ? 'Planned Dates' :
                        dateMode === 'actual' ? 'Actual Dates' : 'Both'}
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <span>🔴 Critical</span>
                    <span>🔵 In Progress</span>
                    <span>🟢 Complete</span>
                    <span>⋮ Today</span>
                </div>
            </div>
        </div>
    );
};

export default GanttChart;