import React, { useCallback, useEffect, useMemo, useState } from 'react';

interface Schedule {
    id: number;
    name: string;
    description: string;
    project_id: number;
    file_name?: string;
    file_size?: number;
    total_activities: number;
    total_relationships: number;
    total_wbs_items: number;
    project_start_date?: string;
    project_finish_date?: string;
    data_date?: string;
    proj_id: string;
    proj_short_name: string;
    status: string;
    created_date: string;
    created_by: string;
}

interface Activity {
    task_id: string;
    task_name: string;
    task_code: string;
    activity_code: string;
    wbs_id: string;
    wbs_code: string;
    proj_id: string;
    duration_days: number;
    remaining_duration: number;
    original_duration: number;
    early_start_date: string | null;
    early_end_date: string | null;
    late_start_date: string | null;
    late_end_date: string | null;
    actual_start_date: string | null;
    actual_end_date: string | null;
    target_start_date: string | null;
    target_end_date: string | null;
    baseline_start_date: string | null;
    baseline_end_date: string | null;
    progress_pct: number;
    percent_complete: number;
    total_float_days: number;
    free_float_days: number;
    task_type: string;
    status_code: string;
    hierarchy_path: string;
    activity_codes?: Record<string, string>;
    udf_values?: Record<string, any>;
    resource_names?: string;
    constraint_type?: string;
    constraint_date?: string;
}

interface WBSItem {
    wbs_id: string;
    wbs_name: string;
    wbs_code: string;
    wbs_short_name: string;
    parent_wbs_id: string | null;
    proj_id: string;
    proj_node_flag: string;
    level: number;
    sort_order: number;
    full_path: string;
}

interface TreeNode {
    id: string;
    type: 'project' | 'wbs' | 'activity';
    code: string;
    name: string;
    level: number;
    isExpanded: boolean;
    hasChildren: boolean;
    children: TreeNode[];
    activityCount?: number;

    // Activity/WBS properties
    task_id?: string;
    wbs_id?: string;
    duration_days?: number;
    progress_pct?: number;
    total_float_days?: number;
    early_start_date?: string | null;
    early_end_date?: string | null;
    target_start_date?: string | null;
    target_end_date?: string | null;
    actual_start_date?: string | null;
    actual_end_date?: string | null;
    task_type?: string;
    status_code?: string;
    remaining_duration?: number;
    resource_names?: string;
    activity_codes?: Record<string, string>;
    udf_values?: Record<string, any>;
    constraint_type?: string;
}

interface ProjectSummary {
    project_start: string | null;
    project_finish: string | null;
    total_duration: number;
    overall_progress: number;
    critical_activities: number;
    completed_activities: number;
    in_progress_activities: number;
    not_started_activities: number;
    total_activities: number;
    activities_with_codes: number;
    activities_with_udfs: number;
    unique_activity_code_types: string[];
    unique_udf_types: string[];
}

interface ActivitiesPageProps {
    schedule: Schedule;
    onBackToSchedules: () => void;
}

const EnhancedActivitiesPage: React.FC<ActivitiesPageProps> = ({ schedule, onBackToSchedules }) => {
    const [activities, setActivities] = useState<Activity[]>([]);
    const [wbsStructure, setWbsStructure] = useState<WBSItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedWBS, setExpandedWBS] = useState<Set<string>>(new Set());
    const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null);

    // Enhanced search and filter states
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [activityCodeFilter, setActivityCodeFilter] = useState<string>('');
    const [showEnhancedColumns, setShowEnhancedColumns] = useState(false);
    const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);

    // Load activities with enhanced data
    const fetchActivities = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            console.log('🔍 Loading enhanced activities...');

            const params = new URLSearchParams({
                search: searchTerm,
                status: statusFilter,
                include_codes: 'true',
                include_udfs: 'true'
            });

            const response = await fetch(`http://localhost:5000/api/schedules/${schedule.id}/activities?${params}`);

            if (!response.ok) {
                throw new Error(`Failed to load activities: ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                console.log(`✅ Loaded ${data.activities?.length || 0} enhanced activities`);

                setActivities(data.activities || []);
                setWbsStructure(data.wbs_structure || []);

                // Calculate enhanced project summary
                const summary = calculateEnhancedProjectSummary(data.activities || [], data.enhanced_data_stats);
                setProjectSummary(summary);

                // Auto-expand first few levels
                if (data.wbs_structure && data.wbs_structure.length > 0) {
                    const rootWBS = data.wbs_structure
                        .filter((wbs: WBSItem) => wbs.proj_node_flag === 'Y' || wbs.level <= 1)
                        .map((wbs: WBSItem) => wbs.wbs_id);
                    setExpandedWBS(new Set(['project-root', ...rootWBS.slice(0, 3)]));
                }
            } else {
                throw new Error(data.error || 'Failed to load activities');
            }

        } catch (err) {
            console.error('❌ Error loading activities:', err);
            setError(err instanceof Error ? err.message : 'Failed to load activities');
        } finally {
            setLoading(false);
        }
    }, [schedule.id, searchTerm, statusFilter]);

    useEffect(() => {
        const timer = setTimeout(() => {
            fetchActivities();
        }, 300);

        return () => clearTimeout(timer);
    }, [fetchActivities]);

    // Calculate enhanced project summary
    const calculateEnhancedProjectSummary = (activities: Activity[], enhancedStats: any): ProjectSummary => {
        if (activities.length === 0) {
            return {
                project_start: null,
                project_finish: null,
                total_duration: 0,
                overall_progress: 0,
                critical_activities: 0,
                completed_activities: 0,
                in_progress_activities: 0,
                not_started_activities: 0,
                total_activities: 0,
                activities_with_codes: 0,
                activities_with_udfs: 0,
                unique_activity_code_types: [],
                unique_udf_types: []
            };
        }

        const validActivities = activities.filter(a => a.early_start_date && a.early_end_date);

        const project_start = validActivities.length > 0 ?
            new Date(Math.min(...validActivities.map(a => new Date(a.early_start_date!).getTime()))).toISOString() : null;

        const project_finish = validActivities.length > 0 ?
            new Date(Math.max(...validActivities.map(a => new Date(a.early_end_date!).getTime()))).toISOString() : null;

        const total_duration = activities.reduce((sum, a) => sum + (a.duration_days || 0), 0);
        const overall_progress = total_duration > 0 ?
            activities.reduce((sum, a) => sum + ((a.progress_pct || 0) * (a.duration_days || 0)), 0) / total_duration : 0;

        // Enhanced statistics
        const activities_with_codes = activities.filter(a => a.activity_codes && Object.keys(a.activity_codes).length > 0).length;
        const activities_with_udfs = activities.filter(a => a.udf_values && Object.keys(a.udf_values).length > 0).length;

        // Collect unique types
        const codeTypes = new Set<string>();
        const udfTypes = new Set<string>();

        activities.forEach(activity => {
            if (activity.activity_codes) {
                Object.keys(activity.activity_codes).forEach(type => codeTypes.add(type));
            }
            if (activity.udf_values) {
                Object.keys(activity.udf_values).forEach(type => udfTypes.add(type));
            }
        });

        return {
            project_start,
            project_finish,
            total_duration,
            overall_progress: Math.round(overall_progress),
            critical_activities: activities.filter(a => (a.total_float_days || 0) === 0).length,
            completed_activities: activities.filter(a => (a.progress_pct || 0) >= 100).length,
            in_progress_activities: activities.filter(a => (a.progress_pct || 0) > 0 && (a.progress_pct || 0) < 100).length,
            not_started_activities: activities.filter(a => (a.progress_pct || 0) === 0).length,
            total_activities: activities.length,
            activities_with_codes,
            activities_with_udfs,
            unique_activity_code_types: Array.from(codeTypes),
            unique_udf_types: Array.from(udfTypes)
        };
    };

    // Build enhanced P6-style hierarchy
    const treeData = useMemo(() => {
        if (wbsStructure.length === 0 || activities.length === 0) {
            return [];
        }

        console.log('🌳 Building P6-style hierarchy...');

        const activitiesByWBS = new Map<string, Activity[]>();
        activities.forEach(activity => {
            const wbsId = activity.wbs_id;
            if (!activitiesByWBS.has(wbsId)) {
                activitiesByWBS.set(wbsId, []);
            }
            activitiesByWBS.get(wbsId)!.push(activity);
        });

        const nodes: TreeNode[] = [];

        // Add project root with enhanced info
        if (projectSummary) {
            const projectNode: TreeNode = {
                id: 'project-root',
                type: 'project',
                code: schedule.proj_id || 'PROJ',
                name: schedule.proj_short_name || schedule.name,
                level: 0,
                isExpanded: expandedWBS.has('project-root'),
                hasChildren: true,
                children: [],
                activityCount: activities.length,
                progress_pct: projectSummary.overall_progress,
                early_start_date: projectSummary.project_start,
                early_end_date: projectSummary.project_finish,
                duration_days: projectSummary.total_duration,
                task_type: 'Project'
            };
            nodes.push(projectNode);

            if (projectNode.isExpanded) {
                buildWBSNodes(null, 1);
            }
        }

        function buildWBSNodes(parentId: string | null, level: number) {
            const childWBS = wbsStructure
                .filter(wbs => {
                    if (parentId === null) {
                        return wbs.proj_node_flag === 'Y' || wbs.level === 0 || !wbs.parent_wbs_id;
                    }
                    return wbs.parent_wbs_id === parentId;
                })
                .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || (a.wbs_code || a.wbs_name).localeCompare(b.wbs_code || b.wbs_name));

            childWBS.forEach(wbs => {
                const wbsActivities = activitiesByWBS.get(wbs.wbs_id) || [];
                const hasChildWBS = wbsStructure.some(w => w.parent_wbs_id === wbs.wbs_id);
                const isExpanded = expandedWBS.has(wbs.wbs_id);

                // Calculate WBS rollups
                const allDescendantActivities = getAllDescendantActivities(wbs.wbs_id);
                const rollupData = calculateWBSRollups(allDescendantActivities);

                const wbsNode: TreeNode = {
                    id: `wbs-${wbs.wbs_id}`,
                    type: 'wbs',
                    code: wbs.wbs_code || `L${wbs.level}`,
                    name: wbs.wbs_name || 'Unnamed WBS',
                    level: level,
                    isExpanded: isExpanded,
                    hasChildren: hasChildWBS || wbsActivities.length > 0,
                    children: [],
                    activityCount: allDescendantActivities.length,
                    wbs_id: wbs.wbs_id,
                    ...rollupData,
                    task_type: 'WBS'
                };

                nodes.push(wbsNode);

                if (isExpanded) {
                    // Add child WBS first
                    if (hasChildWBS) {
                        buildWBSNodes(wbs.wbs_id, level + 1);
                    }

                    // Add direct activities
                    wbsActivities
                        .sort((a, b) => {
                            // Sort by activity code, then by start date
                            if (a.activity_code && b.activity_code) {
                                const codeCompare = a.activity_code.localeCompare(b.activity_code);
                                if (codeCompare !== 0) return codeCompare;
                            }
                            const dateA = a.early_start_date ? new Date(a.early_start_date).getTime() : 0;
                            const dateB = b.early_start_date ? new Date(b.early_start_date).getTime() : 0;
                            return dateA - dateB;
                        })
                        .forEach(activity => {
                            nodes.push({
                                id: `activity-${activity.task_id}`,
                                type: 'activity',
                                code: activity.activity_code || activity.task_id,
                                name: activity.task_name || 'Unnamed Activity',
                                level: level + 1,
                                isExpanded: false,
                                hasChildren: false,
                                children: [],
                                task_id: activity.task_id,
                                wbs_id: activity.wbs_id,
                                duration_days: activity.duration_days,
                                remaining_duration: activity.remaining_duration,
                                progress_pct: activity.progress_pct,
                                total_float_days: activity.total_float_days,
                                early_start_date: activity.early_start_date,
                                early_end_date: activity.early_end_date,
                                target_start_date: activity.target_start_date,
                                target_end_date: activity.target_end_date,
                                actual_start_date: activity.actual_start_date,
                                actual_end_date: activity.actual_end_date,
                                task_type: activity.task_type,
                                status_code: activity.status_code,
                                resource_names: activity.resource_names,
                                activity_codes: activity.activity_codes,
                                udf_values: activity.udf_values,
                                constraint_type: activity.constraint_type
                            });
                        });
                }
            });
        }

        function getAllDescendantActivities(wbsId: string): Activity[] {
            const directActivities = activitiesByWBS.get(wbsId) || [];
            const childWBS = wbsStructure.filter(wbs => wbs.parent_wbs_id === wbsId);
            const childActivities = childWBS.flatMap(childWbs => getAllDescendantActivities(childWbs.wbs_id));
            return [...directActivities, ...childActivities];
        }

        function calculateWBSRollups(descendantActivities: Activity[]) {
            if (descendantActivities.length === 0) {
                return {
                    progress_pct: 0,
                    early_start_date: null,
                    early_end_date: null,
                    duration_days: 0,
                    total_float_days: 0
                };
            }

            const validActivities = descendantActivities.filter(a => a.early_start_date && a.early_end_date);
            const startDate = validActivities.length > 0 ?
                new Date(Math.min(...validActivities.map(a => new Date(a.early_start_date!).getTime()))).toISOString() : null;
            const endDate = validActivities.length > 0 ?
                new Date(Math.max(...validActivities.map(a => new Date(a.early_end_date!).getTime()))).toISOString() : null;

            const totalDuration = descendantActivities.reduce((sum, a) => sum + (a.duration_days || 0), 0);
            const avgProgress = totalDuration > 0 ?
                descendantActivities.reduce((sum, a) => sum + ((a.progress_pct || 0) * (a.duration_days || 0)), 0) / totalDuration : 0;
            const minFloat = descendantActivities.length > 0 ?
                Math.min(...descendantActivities.map(a => a.total_float_days || 0)) : 0;

            return {
                progress_pct: Math.round(avgProgress),
                early_start_date: startDate,
                early_end_date: endDate,
                duration_days: totalDuration,
                total_float_days: minFloat
            };
        }

        console.log(`✅ Built P6 hierarchy with ${nodes.length} nodes`);
        return nodes;
    }, [activities, wbsStructure, expandedWBS, projectSummary, schedule]);

    const toggleWBS = (nodeId: string) => {
        const newExpanded = new Set(expandedWBS);
        if (newExpanded.has(nodeId)) {
            newExpanded.delete(nodeId);
        } else {
            newExpanded.add(nodeId);
        }
        setExpandedWBS(newExpanded);
    };

    const formatDate = (dateStr: string | null | undefined) => {
        if (!dateStr) return '-';
        try {
            return new Date(dateStr).toLocaleDateString('en-US', {
                day: '2-digit',
                month: 'short',
                year: '2-digit'
            });
        } catch {
            return '-';
        }
    };

    const getActivityIcon = (node: TreeNode) => {
        if (node.type === 'project') return '🏗️';
        if (node.type === 'wbs') {
            const colors = ['🟦', '🟩', '🟨', '🟧', '🟪'];
            return colors[node.level % colors.length] || '📁';
        }

        const isCritical = (node.total_float_days || 0) === 0;
        const progress = node.progress_pct || 0;

        if (isCritical) return '🔴';
        if (progress >= 100) return '✅';
        if (progress > 0) return '🟡';
        return '⚪';
    };

    // Render activity codes as badges
    const renderActivityCodes = (activityCodes: Record<string, string> | undefined) => {
        if (!activityCodes || Object.keys(activityCodes).length === 0) return null;

        return (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                {Object.entries(activityCodes).map(([type, value]) => (
                    <span
                        key={type}
                        style={{
                            fontSize: '9px',
                            padding: '2px 6px',
                            backgroundColor: '#e3f2fd',
                            color: '#1976d2',
                            borderRadius: '8px',
                            border: '1px solid #bbdefb',
                            fontWeight: '500'
                        }}
                        title={`${type}: ${value}`}
                    >
                        {type}: {value}
                    </span>
                ))}
            </div>
        );
    };

    // Enhanced loading state
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
                gap: '15px',
                backgroundColor: '#f5f5f5'
            }}>
                <div style={{
                    width: '60px',
                    height: '60px',
                    border: '4px solid #e3e3e3',
                    borderTop: '4px solid #2196F3',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                }} />
                <div>Loading enhanced activities...</div>
                <div style={{ fontSize: '14px', color: '#999' }}>
                    {schedule.total_activities?.toLocaleString()} activities • Enhanced P6 data
                </div>
                <style>
                    {`
                        @keyframes spin {
                            0% { transform: rotate(0deg); }
                            100% { transform: rotate(360deg); }
                        }
                    `}
                </style>
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
                borderRadius: '8px',
                boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
            }}>
                <h3>⚠️ Error Loading Enhanced Activities</h3>
                <p>{error}</p>
                <button
                    onClick={onBackToSchedules}
                    style={{
                        padding: '12px 24px',
                        backgroundColor: '#6c757d',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        marginTop: '20px',
                        fontSize: '14px'
                    }}
                >
                    ← Back to Schedules
                </button>
            </div>
        );
    }

    return (
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#f5f5f5' }}>

            {/* Enhanced Project Summary Header */}
            {projectSummary && (
                <div style={{
                    backgroundColor: '#fff',
                    padding: '16px 24px',
                    borderBottom: '1px solid #e0e0e0',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.08)'
                }}>
                    {/* Project Title */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <h2 style={{ margin: 0, color: '#1a1a1a', fontSize: '20px', fontWeight: '600' }}>
                            🏗️ {schedule.proj_short_name || schedule.name}
                        </h2>
                        <button
                            onClick={onBackToSchedules}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: '#2196F3',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: '500'
                            }}
                        >
                            ← Back to Schedules
                        </button>
                    </div>

                    {/* Enhanced Project Summary Stats */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                        gap: '12px',
                        marginBottom: '12px'
                    }}>
                        <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                            <div style={{ fontSize: '18px', fontWeight: '700', color: '#2196F3' }}>
                                {projectSummary.overall_progress}%
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>Progress</div>
                        </div>

                        <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                            <div style={{ fontSize: '14px', fontWeight: '600', color: '#333' }}>
                                {projectSummary.total_activities}
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>Activities</div>
                        </div>

                        <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#ffebee', borderRadius: '4px' }}>
                            <div style={{ fontSize: '14px', fontWeight: '700', color: '#f44336' }}>
                                {projectSummary.critical_activities}
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>Critical</div>
                        </div>

                        <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#e8f5e8', borderRadius: '4px' }}>
                            <div style={{ fontSize: '14px', fontWeight: '700', color: '#4CAF50' }}>
                                {projectSummary.completed_activities}
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>Complete</div>
                        </div>

                        <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#e3f2fd', borderRadius: '4px' }}>
                            <div style={{ fontSize: '14px', fontWeight: '700', color: '#2196F3' }}>
                                {projectSummary.activities_with_codes}
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>With Codes</div>
                        </div>

                        <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#fff3e0', borderRadius: '4px' }}>
                            <div style={{ fontSize: '14px', fontWeight: '700', color: '#ff9800' }}>
                                {projectSummary.activities_with_udfs}
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>With UDFs</div>
                        </div>
                    </div>

                    {/* Enhanced Search and Controls */}
                    <div style={{
                        display: 'flex',
                        gap: '12px',
                        alignItems: 'center',
                        flexWrap: 'wrap'
                    }}>
                        <input
                            type="text"
                            placeholder="🔍 Search activities, codes, or WBS..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            style={{
                                padding: '6px 12px',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                fontSize: '13px',
                                width: '280px'
                            }}
                        />

                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            style={{
                                padding: '6px 12px',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                fontSize: '13px'
                            }}
                        >
                            <option value="all">All Activities</option>
                            <option value="not_started">Not Started</option>
                            <option value="in_progress">In Progress</option>
                            <option value="completed">Completed</option>
                        </select>

                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                            <input
                                type="checkbox"
                                checked={showEnhancedColumns}
                                onChange={(e) => setShowEnhancedColumns(e.target.checked)}
                            />
                            Enhanced Columns
                        </label>

                        {wbsStructure.length > 0 && (
                            <>
                                <button
                                    onClick={() => {
                                        const allWBS = ['project-root', ...wbsStructure.map(wbs => wbs.wbs_id)];
                                        setExpandedWBS(new Set(allWBS));
                                    }}
                                    style={{
                                        padding: '6px 12px',
                                        backgroundColor: '#4CAF50',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '11px',
                                        fontWeight: '500'
                                    }}
                                >
                                    Expand All
                                </button>

                                <button
                                    onClick={() => setExpandedWBS(new Set(['project-root']))}
                                    style={{
                                        padding: '6px 12px',
                                        backgroundColor: '#757575',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '11px',
                                        fontWeight: '500'
                                    }}
                                >
                                    Collapse All
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Enhanced Activities Table */}
            <div style={{ flex: 1, backgroundColor: 'white', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

                {/* Enhanced Column Headers */}
                <div style={{
                    backgroundColor: '#f8f9fa',
                    borderBottom: '2px solid #dee2e6',
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                    padding: '8px 16px',
                    fontSize: '10px',
                    fontWeight: '700',
                    color: '#495057',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    display: 'grid',
                    gridTemplateColumns: showEnhancedColumns ?
                        '3fr 70px 50px 50px 70px 70px 70px 70px 70px 70px 50px 50px 80px' :
                        '4fr 80px 60px 60px 80px 80px 80px 80px 60px 60px',
                    gap: '6px',
                    alignItems: 'center'
                }}>
                    <div>ACTIVITY / WBS HIERARCHY</div>
                    <div>CODE</div>
                    <div>PROG</div>
                    <div>DUR</div>
                    <div>EARLY START</div>
                    <div>EARLY FINISH</div>
                    {showEnhancedColumns && <div>TARGET START</div>}
                    {showEnhancedColumns && <div>TARGET FINISH</div>}
                    <div>ACTUAL START</div>
                    <div>ACTUAL FINISH</div>
                    {showEnhancedColumns && <div>REM DUR</div>}
                    <div>FLOAT</div>
                    <div>RESOURCES</div>
                </div>

                {/* Enhanced Main Content with P6 Hierarchy */}
                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {treeData.length === 0 ? (
                        <div style={{
                            padding: '40px',
                            textAlign: 'center',
                            color: '#666'
                        }}>
                            <h3>📋 No Activities Found</h3>
                            <p>Try adjusting your search criteria or check if activities are loaded.</p>
                        </div>
                    ) : (
                        treeData.map((node, index) => {
                            const isCritical = node.type === 'activity' && (node.total_float_days || 0) === 0;
                            const isWBS = node.type === 'wbs';
                            const isProject = node.type === 'project';
                            const indentWidth = node.level * 16;

                            return (
                                <div
                                    key={node.id}
                                    style={{
                                        padding: '6px 16px',
                                        borderBottom: '1px solid #f0f0f0',
                                        backgroundColor: isProject ? '#e3f2fd' :
                                            isWBS ? '#f8f9fa' :
                                                (index % 2 === 0 ? '#fafbfc' : 'white'),
                                        borderLeft: isCritical ? '3px solid #f44336' :
                                            isProject ? '3px solid #1976d2' :
                                                isWBS ? '3px solid #2196F3' :
                                                    '3px solid transparent',
                                        cursor: (isProject || (isWBS && node.hasChildren)) ? 'pointer' : 'default',
                                        display: 'grid',
                                        gridTemplateColumns: showEnhancedColumns ?
                                            '3fr 70px 50px 50px 70px 70px 70px 70px 70px 70px 50px 50px 80px' :
                                            '4fr 80px 60px 60px 80px 80px 80px 80px 60px 60px',
                                        gap: '6px',
                                        alignItems: 'center',
                                        fontSize: '11px',
                                        minHeight: '36px',
                                        transition: 'background-color 0.15s ease'
                                    }}
                                    onClick={() => {
                                        if (isProject) toggleWBS('project-root');
                                        else if (isWBS && node.hasChildren) toggleWBS(node.id.replace('wbs-', ''));
                                        else if (node.type === 'activity') {
                                            // Find the full activity data for details
                                            const fullActivity = activities.find(a => a.task_id === node.task_id);
                                            if (fullActivity) setSelectedActivity(fullActivity);
                                        }
                                    }}
                                >
                                    {/* Enhanced Activity/WBS Name with P6-style hierarchy */}
                                    <div style={{ paddingLeft: `${indentWidth}px` }}>
                                        <div style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px'
                                        }}>
                                            {(isProject || (isWBS && node.hasChildren)) && (
                                                <span style={{
                                                    fontSize: '9px',
                                                    color: isProject ? '#1976d2' : '#2196F3',
                                                    minWidth: '10px',
                                                    fontWeight: 'bold'
                                                }}>
                                                    {node.isExpanded ? '▼' : '▶'}
                                                </span>
                                            )}

                                            <span style={{ fontSize: '12px' }}>
                                                {getActivityIcon(node)}
                                            </span>

                                            <div style={{ flex: 1 }}>
                                                <div style={{
                                                    fontWeight: isProject ? '700' : isWBS ? '600' : '400',
                                                    color: isProject ? '#1976d2' :
                                                        isWBS ? '#1976d2' :
                                                            isCritical ? '#f44336' : '#333',
                                                    fontSize: isProject ? '12px' : '11px',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap'
                                                }}>
                                                    {node.name}
                                                </div>

                                                {/* Enhanced: Show activity codes for activities */}
                                                {node.type === 'activity' && node.activity_codes && (
                                                    renderActivityCodes(node.activity_codes)
                                                )}
                                            </div>

                                            {isCritical && (
                                                <span style={{
                                                    fontSize: '8px',
                                                    color: '#f44336',
                                                    fontWeight: '700',
                                                    backgroundColor: '#ffebee',
                                                    padding: '1px 3px',
                                                    borderRadius: '2px'
                                                }}>
                                                    CRIT
                                                </span>
                                            )}
                                        </div>

                                        {(isProject || isWBS) && node.activityCount && (
                                            <div style={{
                                                fontSize: '9px',
                                                color: '#666',
                                                marginTop: '1px',
                                                marginLeft: indentWidth > 0 ? '14px' : '14px'
                                            }}>
                                                {node.activityCount} activities
                                            </div>
                                        )}
                                    </div>

                                    {/* Activity/WBS Code */}
                                    <div style={{
                                        fontSize: '10px',
                                        fontFamily: 'monospace',
                                        color: isProject ? '#1976d2' : isWBS ? '#1976d2' : '#666',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        fontWeight: (isProject || isWBS) ? '600' : '400'
                                    }}>
                                        {node.code}
                                    </div>

                                    {/* Progress */}
                                    <div style={{ textAlign: 'center' }}>
                                        <div style={{
                                            fontSize: '10px',
                                            fontWeight: '600',
                                            color: (node.progress_pct || 0) >= 100 ? '#4CAF50' :
                                                (node.progress_pct || 0) > 0 ? '#2196F3' : '#757575',
                                            marginBottom: '1px'
                                        }}>
                                            {Math.round(node.progress_pct || 0)}%
                                        </div>
                                        <div style={{
                                            width: '100%',
                                            height: '2px',
                                            backgroundColor: '#e0e0e0',
                                            borderRadius: '1px',
                                            overflow: 'hidden'
                                        }}>
                                            <div style={{
                                                width: `${node.progress_pct || 0}%`,
                                                height: '100%',
                                                backgroundColor: (node.progress_pct || 0) >= 100 ? '#4CAF50' :
                                                    (node.progress_pct || 0) > 0 ? '#2196F3' : '#e0e0e0',
                                                borderRadius: '1px'
                                            }} />
                                        </div>
                                    </div>

                                    {/* Duration */}
                                    <div style={{
                                        textAlign: 'center',
                                        fontWeight: '600',
                                        fontSize: '10px',
                                        color: '#333'
                                    }}>
                                        {node.duration_days ? `${Math.round(node.duration_days)}d` : '-'}
                                    </div>

                                    {/* Early Start */}
                                    <div style={{
                                        fontSize: '9px',
                                        fontFamily: 'monospace',
                                        color: '#555',
                                        textAlign: 'center'
                                    }}>
                                        {formatDate(node.early_start_date)}
                                    </div>

                                    {/* Early Finish */}
                                    <div style={{
                                        fontSize: '9px',
                                        fontFamily: 'monospace',
                                        color: '#555',
                                        textAlign: 'center'
                                    }}>
                                        {formatDate(node.early_end_date)}
                                    </div>

                                    {/* Enhanced Columns */}
                                    {showEnhancedColumns && (
                                        <>
                                            {/* Target Start */}
                                            <div style={{
                                                fontSize: '9px',
                                                fontFamily: 'monospace',
                                                color: '#9c27b0',
                                                textAlign: 'center'
                                            }}>
                                                {formatDate(node.target_start_date)}
                                            </div>

                                            {/* Target Finish */}
                                            <div style={{
                                                fontSize: '9px',
                                                fontFamily: 'monospace',
                                                color: '#9c27b0',
                                                textAlign: 'center'
                                            }}>
                                                {formatDate(node.target_end_date)}
                                            </div>
                                        </>
                                    )}

                                    {/* Actual Start */}
                                    <div style={{
                                        fontSize: '9px',
                                        fontFamily: 'monospace',
                                        color: node.actual_start_date ? '#4CAF50' : '#ccc',
                                        textAlign: 'center',
                                        fontWeight: node.actual_start_date ? '600' : '400'
                                    }}>
                                        {formatDate(node.actual_start_date) || '-'}
                                    </div>

                                    {/* Actual Finish */}
                                    <div style={{
                                        fontSize: '9px',
                                        fontFamily: 'monospace',
                                        color: node.actual_end_date ? '#4CAF50' : '#ccc',
                                        textAlign: 'center',
                                        fontWeight: node.actual_end_date ? '600' : '400'
                                    }}>
                                        {formatDate(node.actual_end_date) || '-'}
                                    </div>

                                    {/* Enhanced: Remaining Duration */}
                                    {showEnhancedColumns && (
                                        <div style={{
                                            textAlign: 'center',
                                            fontSize: '10px',
                                            color: '#ff5722',
                                            fontWeight: '600'
                                        }}>
                                            {node.remaining_duration ? `${Math.round(node.remaining_duration)}d` : '-'}
                                        </div>
                                    )}

                                    {/* Float */}
                                    <div style={{ textAlign: 'center' }}>
                                        <span style={{
                                            fontSize: '9px',
                                            fontWeight: '600',
                                            color: (node.total_float_days || 0) === 0 ? '#f44336' :
                                                (node.total_float_days || 0) <= 5 ? '#ff9800' : '#4CAF50',
                                            padding: '1px 3px',
                                            borderRadius: '2px',
                                            backgroundColor: (node.total_float_days || 0) === 0 ? '#ffebee' :
                                                (node.total_float_days || 0) <= 5 ? '#fff3e0' : '#e8f5e8'
                                        }}>
                                            {Math.round(node.total_float_days || 0)}d
                                        </span>
                                    </div>

                                    {/* Resources */}
                                    <div style={{
                                        fontSize: '9px',
                                        color: '#666',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap'
                                    }}>
                                        {node.resource_names || '-'}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Enhanced Status Bar */}
            <div style={{
                backgroundColor: '#f5f5f5',
                padding: '8px 24px',
                borderTop: '1px solid #e0e0e0',
                fontSize: '10px',
                color: '#666',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
            }}>
                <div>
                    P6 Hierarchy View • {treeData.filter(n => n.type === 'activity').length} activities displayed
                    {projectSummary && (
                        <>
                            • {projectSummary.activities_with_codes} with codes
                            • {projectSummary.unique_activity_code_types.length} code types
                        </>
                    )}
                    {searchTerm && ` • Search: "${searchTerm}"`}
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <span>🔴 Critical • ✅ Complete • 🟡 In Progress • ⚪ Not Started • 🏗️ Project • 📁 WBS</span>
                </div>
            </div>

            {/* Activity Details Modal */}
            {selectedActivity && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.5)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000
                }}
                    onClick={() => setSelectedActivity(null)}>
                    <div style={{
                        backgroundColor: 'white',
                        padding: '24px',
                        borderRadius: '8px',
                        maxWidth: '600px',
                        maxHeight: '80vh',
                        overflow: 'auto',
                        margin: '20px'
                    }}
                        onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ margin: '0 0 16px 0', color: '#333' }}>
                            Activity Details: {selectedActivity.activity_code || selectedActivity.task_id}
                        </h3>

                        <div style={{ marginBottom: '16px' }}>
                            <strong>{selectedActivity.task_name}</strong>
                        </div>

                        {/* Activity Codes */}
                        {selectedActivity.activity_codes && Object.keys(selectedActivity.activity_codes).length > 0 && (
                            <div style={{ marginBottom: '16px' }}>
                                <h4 style={{ margin: '0 0 8px 0', color: '#1976d2' }}>Activity Codes</h4>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                    {Object.entries(selectedActivity.activity_codes).map(([type, value]) => (
                                        <span key={type} style={{
                                            padding: '4px 8px',
                                            backgroundColor: '#e3f2fd',
                                            color: '#1976d2',
                                            borderRadius: '4px',
                                            fontSize: '12px',
                                            border: '1px solid #bbdefb'
                                        }}>
                                            <strong>{type}:</strong> {value}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* UDF Values */}
                        {selectedActivity.udf_values && Object.keys(selectedActivity.udf_values).length > 0 && (
                            <div style={{ marginBottom: '16px' }}>
                                <h4 style={{ margin: '0 0 8px 0', color: '#ff9800' }}>User Defined Fields</h4>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                                    {Object.entries(selectedActivity.udf_values).map(([field, value]) => (
                                        <div key={field} style={{
                                            padding: '6px',
                                            backgroundColor: '#fff3e0',
                                            borderRadius: '4px',
                                            fontSize: '12px'
                                        }}>
                                            <strong>{field}:</strong> {String(value)}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Enhanced Dates */}
                        <div style={{ marginBottom: '16px' }}>
                            <h4 style={{ margin: '0 0 8px 0', color: '#4CAF50' }}>Dates</h4>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                                <div><strong>Early Start:</strong> {formatDate(selectedActivity.early_start_date)}</div>
                                <div><strong>Early Finish:</strong> {formatDate(selectedActivity.early_end_date)}</div>
                                <div><strong>Target Start:</strong> {formatDate(selectedActivity.target_start_date)}</div>
                                <div><strong>Target Finish:</strong> {formatDate(selectedActivity.target_end_date)}</div>
                                <div><strong>Actual Start:</strong> {formatDate(selectedActivity.actual_start_date)}</div>
                                <div><strong>Actual Finish:</strong> {formatDate(selectedActivity.actual_end_date)}</div>
                            </div>
                        </div>

                        <button
                            onClick={() => setSelectedActivity(null)}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: '#2196F3',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer'
                            }}
                        >
                            Close
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default EnhancedActivitiesPage;