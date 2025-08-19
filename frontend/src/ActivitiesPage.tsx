import React, { useEffect, useMemo, useState } from 'react';

interface Schedule {
    id: number;
    name: string;
    total_activities: number;
    total_relationships: number;
}

interface Activity {
    task_id: string;
    task_name: string;
    wbs_id: string;
    duration_days: number;
    early_start_date: string | null;
    early_end_date: string | null;
    late_start_date: string | null;
    late_end_date: string | null;
    actual_start_date: string | null;
    actual_end_date: string | null;
    progress_pct: number;
    total_float_days: number;
    free_float_days: number;
    task_type: string;
    status_code: string;
}

interface WBSItem {
    wbs_id: string;
    wbs_name: string;
    parent_wbs_id: string | null;
    proj_id: string | number;
}

interface ProjectInfo {
    project_id: number;
    project_name: string;
    schedule_name: string;
    schedule_id: number;
}

interface HierarchyNode {
    id: string;
    type: 'project' | 'wbs' | 'activity';
    name: string;
    level: number;
    expanded?: boolean;
    isParent: boolean;
    children?: number;
    activities?: Activity[];
    parent?: string;
    wbs_id?: string;
    // Activity properties (when type === 'activity')
    task_id?: string;
    task_name?: string;
    duration_days?: number;
    early_start_date?: string | null;
    early_end_date?: string | null;
    late_start_date?: string | null;
    late_end_date?: string | null;
    actual_start_date?: string | null;
    actual_end_date?: string | null;
    progress_pct?: number;
    total_float_days?: number;
    free_float_days?: number;
    task_type?: string;
    status_code?: string;
}

interface ActivitiesPageProps {
    schedule: Schedule;
    onBackToSchedules: () => void;
}

const ActivitiesPage: React.FC<ActivitiesPageProps> = ({ schedule, onBackToSchedules }) => {
    const [activities, setActivities] = useState<Activity[]>([]);
    const [wbsStructure, setWbsStructure] = useState<WBSItem[]>([]);
    const [projectInfo, setProjectInfo] = useState<ProjectInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [totalActivities, setTotalActivities] = useState(0);
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
    const [debugInfo, setDebugInfo] = useState<string>('');

    // Load activities and WBS structure from API
    useEffect(() => {
        const fetchActivities = async () => {
            try {
                setLoading(true);
                setError(null);
                setDebugInfo('Starting API call...');

                console.log('Fetching activities for schedule:', schedule.id);
                const response = await fetch(`http://localhost:5000/api/schedules/${schedule.id}/activities?per_page=2000&page=1`);

                console.log('Response status:', response.status);
                setDebugInfo(`API Response Status: ${response.status}`);

                if (!response.ok) {
                    throw new Error(`Failed to load activities: ${response.status} ${response.statusText}`);
                }

                const data = await response.json();
                console.log('API Response:', data);

                if (data.success) {
                    console.log('Activities received:', data.activities?.length || 0);
                    console.log('WBS structure received:', data.wbs_structure?.length || 0);
                    console.log('Project info:', data.project_info);

                    setActivities(data.activities || []);
                    setWbsStructure(data.wbs_structure || []);
                    setProjectInfo(data.project_info || null);
                    setTotalActivities(data.pagination?.total || data.activities?.length || 0);

                    setDebugInfo(`✅ Loaded ${data.activities?.length || 0} activities, ${data.wbs_structure?.length || 0} WBS items`);

                    // Auto-expand first few levels of WBS
                    if (data.wbs_structure && data.wbs_structure.length > 0) {
                        const rootWBS = data.wbs_structure
                            .filter((wbs: WBSItem) => !wbs.parent_wbs_id || wbs.parent_wbs_id === wbs.proj_id)
                            .map((wbs: WBSItem) => wbs.wbs_id);

                        console.log('Root WBS items to expand:', rootWBS);
                        setExpandedNodes(new Set([
                            'project-root',
                            ...rootWBS.slice(0, 5) // Expand first 5 root WBS
                        ]));
                    } else {
                        setExpandedNodes(new Set(['project-root']));
                    }

                } else {
                    throw new Error(data.error || 'API returned success: false');
                }

            } catch (err) {
                console.error('Error loading activities:', err);
                const errorMessage = err instanceof Error ? err.message : 'Failed to load activities';
                setError(errorMessage);
                setDebugInfo(`❌ Error: ${errorMessage}`);
            } finally {
                setLoading(false);
            }
        };

        fetchActivities();
    }, [schedule.id]);

    // Build proper Primavera P6 hierarchy: Project → WBS Levels → Activities
    const hierarchy = useMemo(() => {
        console.log('🏗️ Building P6 hierarchy with:', {
            activitiesCount: activities.length,
            wbsCount: wbsStructure.length,
            projectInfo,
            expandedNodes: Array.from(expandedNodes)
        });

        if (!projectInfo) {
            console.log('❌ No project info available');
            return [];
        }

        const hierarchyArray: HierarchyNode[] = [];

        // Create WBS lookup maps
        const wbsMap = new Map<string, WBSItem>();
        wbsStructure.forEach(wbs => {
            wbsMap.set(wbs.wbs_id, wbs);
        });

        // Group activities by WBS
        const activitiesByWBS = new Map<string, Activity[]>();
        activities.forEach(activity => {
            const wbsId = activity.wbs_id || 'unassigned';
            if (!activitiesByWBS.has(wbsId)) {
                activitiesByWBS.set(wbsId, []);
            }
            activitiesByWBS.get(wbsId)!.push(activity);
        });

        // STEP 1: Add project root node
        const projectNode: HierarchyNode = {
            id: 'project-root',
            type: 'project',
            name: `📊 ${projectInfo.project_name} - ${projectInfo.schedule_name}`,
            level: 0,
            expanded: expandedNodes.has('project-root'),
            isParent: true,
            children: wbsStructure.length
        };
        hierarchyArray.push(projectNode);

        // STEP 2: Build WBS hierarchy recursively if project is expanded
        if (projectNode.expanded) {

            // Function to calculate WBS summary statistics
            const calculateWBSStats = (wbsId: string, allDescendantActivities: Activity[]) => {
                if (allDescendantActivities.length === 0) {
                    return {
                        totalDuration: 0,
                        avgProgress: 0,
                        minFloat: 0,
                        startDate: null,
                        endDate: null
                    };
                }

                const validActivities = allDescendantActivities.filter(a => a.early_start_date && a.early_end_date);
                const startDate = validActivities.length > 0 ?
                    new Date(Math.min(...validActivities.map(a => new Date(a.early_start_date!).getTime()))) : null;
                const endDate = validActivities.length > 0 ?
                    new Date(Math.max(...validActivities.map(a => new Date(a.early_end_date!).getTime()))) : null;

                const totalDuration = allDescendantActivities.reduce((sum, a) => sum + (a.duration_days || 0), 0);
                const avgProgress = allDescendantActivities.length > 0 ?
                    allDescendantActivities.reduce((sum, a) => sum + (a.progress_pct || 0), 0) / allDescendantActivities.length : 0;
                const minFloat = allDescendantActivities.length > 0 ?
                    Math.min(...allDescendantActivities.map(a => a.total_float_days || 0)) : 0;

                return {
                    totalDuration,
                    avgProgress,
                    minFloat,
                    startDate,
                    endDate
                };
            };

            // Function to get all descendant activities for a WBS (including child WBS activities)
            const getAllDescendantActivities = (wbsId: string): Activity[] => {
                const directActivities = activitiesByWBS.get(wbsId) || [];

                // Find child WBS items
                const childWBS = wbsStructure.filter(wbs => wbs.parent_wbs_id === wbsId);
                const childActivities = childWBS.flatMap(childWbs => getAllDescendantActivities(childWbs.wbs_id));

                return [...directActivities, ...childActivities];
            };

            // Recursive function to build WBS tree
            const buildWBSTree = (parentWbsId: string | null, level: number) => {
                // Find WBS items that are children of the current parent
                const childrenWBS = wbsStructure.filter(wbs => {
                    if (parentWbsId === null) {
                        // Root level: parent is null, project ID, or empty string
                        return !wbs.parent_wbs_id ||
                            wbs.parent_wbs_id === projectInfo.project_id?.toString() ||
                            wbs.parent_wbs_id === projectInfo.schedule_id?.toString();
                    }
                    return wbs.parent_wbs_id === parentWbsId;
                });

                // Sort children by WBS name for better organization
                childrenWBS.sort((a, b) => a.wbs_name.localeCompare(b.wbs_name));

                childrenWBS.forEach(wbs => {
                    // Get all activities for this WBS and its descendants
                    const allDescendantActivities = getAllDescendantActivities(wbs.wbs_id);
                    const directActivities = activitiesByWBS.get(wbs.wbs_id) || [];

                    // Calculate WBS summary statistics
                    const stats = calculateWBSStats(wbs.wbs_id, allDescendantActivities);

                    // Create WBS node
                    const wbsNode: HierarchyNode = {
                        id: `wbs-${wbs.wbs_id}`,
                        type: 'wbs',
                        name: `📁 ${wbs.wbs_name}`,
                        level: level,
                        children: directActivities.length,
                        expanded: expandedNodes.has(wbs.wbs_id),
                        isParent: true,
                        activities: directActivities,
                        wbs_id: wbs.wbs_id,
                        parent: parentWbsId || 'project-root',
                        duration_days: stats.totalDuration,
                        early_start_date: stats.startDate?.toISOString() || null,
                        early_end_date: stats.endDate?.toISOString() || null,
                        progress_pct: Math.round(stats.avgProgress),
                        total_float_days: stats.minFloat,
                        task_type: 'WBS',
                        status_code: 'WBS'
                    };

                    hierarchyArray.push(wbsNode);

                    // Add direct activities if WBS is expanded
                    if (wbsNode.expanded && directActivities.length > 0) {
                        directActivities
                            .sort((a, b) => {
                                // Sort by start date, then by task_id
                                if (a.early_start_date && b.early_start_date) {
                                    const dateA = new Date(a.early_start_date).getTime();
                                    const dateB = new Date(b.early_start_date).getTime();
                                    if (dateA !== dateB) return dateA - dateB;
                                }
                                return a.task_id.localeCompare(b.task_id);
                            })
                            .forEach(activity => {
                                hierarchyArray.push({
                                    id: activity.task_id,
                                    type: 'activity',
                                    name: activity.task_name || 'Unnamed Activity',
                                    level: level + 1,
                                    isParent: false,
                                    parent: wbs.wbs_id,
                                    ...activity
                                });
                            });
                    }

                    // Recursively add child WBS
                    buildWBSTree(wbs.wbs_id, level + 1);
                });
            };

            // Start building WBS tree from root level
            buildWBSTree(null, 1);

            // Handle unassigned activities (activities without valid WBS)
            const unassignedActivities = activitiesByWBS.get('unassigned') || [];
            if (unassignedActivities.length > 0) {
                const unassignedNode: HierarchyNode = {
                    id: 'wbs-unassigned',
                    type: 'wbs',
                    name: `📁 Unassigned Activities (${unassignedActivities.length})`,
                    level: 1,
                    children: unassignedActivities.length,
                    expanded: expandedNodes.has('unassigned'),
                    isParent: true,
                    activities: unassignedActivities,
                    wbs_id: 'unassigned',
                    parent: 'project-root',
                    task_type: 'WBS',
                    status_code: 'WBS'
                };

                hierarchyArray.push(unassignedNode);

                if (unassignedNode.expanded) {
                    unassignedActivities.forEach(activity => {
                        hierarchyArray.push({
                            id: activity.task_id,
                            type: 'activity',
                            name: activity.task_name || 'Unnamed Activity',
                            level: 2,
                            isParent: false,
                            parent: 'unassigned',
                            ...activity
                        });
                    });
                }
            }
        }

        console.log(`✅ Built hierarchy with ${hierarchyArray.length} items`);
        return hierarchyArray;
    }, [activities, wbsStructure, projectInfo, expandedNodes]);

    // Toggle node expansion (project, WBS, etc.)
    const toggleNode = (nodeId: string) => {
        const newExpanded = new Set(expandedNodes);
        if (newExpanded.has(nodeId)) {
            newExpanded.delete(nodeId);
        } else {
            newExpanded.add(nodeId);
        }
        setExpandedNodes(newExpanded);
    };

    // Format date for display
    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '';
        try {
            return new Date(dateStr).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: '2-digit'
            });
        } catch {
            return '';
        }
    };

    // Get activity status based on progress
    const getActivityStatus = (progress: number) => {
        if (progress >= 100) return 'Complete';
        if (progress > 0) return 'In Progress';
        return 'Not Started';
    };

    // Loading state
    if (loading) {
        return (
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '400px',
                fontSize: '18px',
                color: '#666',
                flexDirection: 'column',
                gap: '10px'
            }}>
                <div>⏳ Loading {schedule.name} activities...</div>
                <div style={{ fontSize: '14px' }}>Total: {schedule.total_activities.toLocaleString()} activities</div>
                <div style={{ fontSize: '12px', color: '#999' }}>{debugInfo}</div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div style={{
                padding: '40px',
                textAlign: 'center',
                color: '#dc3545'
            }}>
                <h3>⚠️ Error Loading Activities</h3>
                <p>{error}</p>
                <div style={{ fontSize: '12px', color: '#666', marginTop: '10px' }}>
                    Debug: {debugInfo}
                </div>
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
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#f8f9fa' }}>
            {/* Header */}
            <div style={{
                backgroundColor: 'white',
                padding: '20px',
                borderBottom: '1px solid #dee2e6',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ margin: '0 0 8px 0', color: '#2c3e50' }}>
                            📊 {projectInfo?.project_name || schedule.name}
                        </h2>
                        <p style={{ margin: 0, color: '#6c757d', fontSize: '14px' }}>
                            {activities.length.toLocaleString()} of {totalActivities.toLocaleString()} activities loaded
                            {wbsStructure.length > 0 && ` • ${wbsStructure.length} WBS items`}
                        </p>
                        {debugInfo && (
                            <p style={{ margin: '5px 0 0 0', color: '#999', fontSize: '12px' }}>
                                {debugInfo}
                            </p>
                        )}
                    </div>

                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        {hierarchy.length > 0 && (
                            <>
                                <button
                                    onClick={() => {
                                        const allNodeIds = [
                                            'project-root',
                                            ...wbsStructure.map(wbs => wbs.wbs_id),
                                            'unassigned'
                                        ];
                                        setExpandedNodes(new Set(allNodeIds));
                                    }}
                                    style={{
                                        padding: '8px 16px',
                                        backgroundColor: '#007bff',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '12px'
                                    }}
                                >
                                    📂 Expand All
                                </button>

                                <button
                                    onClick={() => setExpandedNodes(new Set())}
                                    style={{
                                        padding: '8px 16px',
                                        backgroundColor: '#6c757d',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '12px'
                                    }}
                                >
                                    📁 Collapse All
                                </button>
                            </>
                        )}

                        <button
                            onClick={onBackToSchedules}
                            style={{
                                padding: '12px 24px',
                                backgroundColor: '#6c757d',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '14px',
                                fontWeight: '500'
                            }}
                        >
                            ← Back to Schedules
                        </button>
                    </div>
                </div>
            </div>

            {/* Activities Table */}
            <div style={{ flex: 1, backgroundColor: 'white', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {/* Table Headers */}
                <div style={{
                    padding: '12px 16px',
                    backgroundColor: '#f8f9fa',
                    borderBottom: '2px solid #dee2e6',
                    fontSize: '11px',
                    fontWeight: '700',
                    color: '#495057',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    position: 'sticky',
                    top: 0,
                    zIndex: 10
                }}>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: '4fr 80px 80px 60px 80px 80px 80px 80px 60px',
                        gap: '12px',
                        alignItems: 'center'
                    }}>
                        <div>PROJECT / WBS / ACTIVITY</div>
                        <div>TASK ID</div>
                        <div>DURATION</div>
                        <div>PROGRESS</div>
                        <div>START DATE</div>
                        <div>END DATE</div>
                        <div>ACTUAL START</div>
                        <div>ACTUAL END</div>
                        <div>FLOAT</div>
                    </div>
                </div>

                {/* Hierarchy Display */}
                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {hierarchy.length === 0 ? (
                        <div style={{
                            padding: '40px',
                            textAlign: 'center',
                            color: '#6c757d'
                        }}>
                            <h3>📋 No Hierarchy Data</h3>
                            <p>Unable to build project hierarchy.</p>
                            <p style={{ fontSize: '12px' }}>
                                Activities: {activities.length}, WBS: {wbsStructure.length}
                            </p>
                        </div>
                    ) : (
                        hierarchy.map((node, index) => {
                            const isCritical = (node.total_float_days || 0) === 0 && node.type === 'activity';
                            const isProject = node.type === 'project';
                            const isWBS = node.type === 'wbs';
                            const isActivity = node.type === 'activity';

                            return (
                                <div
                                    key={node.id}
                                    style={{
                                        padding: '10px 16px',
                                        borderBottom: '1px solid #f0f0f0',
                                        fontSize: isProject ? '16px' : isWBS ? '14px' : '13px',
                                        backgroundColor: isProject ? '#e3f2fd' :
                                            isWBS ? '#f8f9fa' :
                                                (index % 2 === 0 ? '#fafbfc' : 'white'),
                                        borderLeft: isCritical ? '4px solid #dc3545' :
                                            isProject ? '4px solid #667eea' :
                                                isWBS ? '4px solid #4a90e2' :
                                                    '4px solid transparent',
                                        fontWeight: isProject ? '700' : isWBS ? '600' : '400'
                                    }}
                                >
                                    <div style={{
                                        display: 'grid',
                                        gridTemplateColumns: '4fr 80px 80px 60px 80px 80px 80px 80px 60px',
                                        gap: '12px',
                                        alignItems: 'center'
                                    }}>

                                        {/* Project / WBS / Activity Name */}
                                        <div style={{ paddingLeft: `${node.level * 24}px` }}>
                                            {(isProject || isWBS) ? (
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    <button
                                                        onClick={() => toggleNode(isProject ? 'project-root' : node.wbs_id!)}
                                                        style={{
                                                            background: 'none',
                                                            border: 'none',
                                                            cursor: 'pointer',
                                                            fontSize: '12px',
                                                            color: isProject ? '#667eea' : '#4a90e2',
                                                            padding: '2px 4px',
                                                            borderRadius: '3px'
                                                        }}
                                                    >
                                                        {node.expanded ? '📂' : '📁'}
                                                    </button>
                                                    <div>
                                                        <div style={{
                                                            fontWeight: isProject ? '800' : '700',
                                                            color: isProject ? '#667eea' : '#4a90e2',
                                                            marginBottom: '2px'
                                                        }}>
                                                            {node.name}
                                                        </div>
                                                        <div style={{
                                                            fontSize: '11px',
                                                            color: '#6c757d'
                                                        }}>
                                                            {isProject ?
                                                                `${totalActivities.toLocaleString()} total activities • ${wbsStructure.length} WBS items` :
                                                                `${node.children} direct activities`
                                                            }
                                                        </div>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div>
                                                    <div style={{
                                                        fontWeight: '500',
                                                        color: isCritical ? '#dc3545' : '#2c3e50',
                                                        marginBottom: '2px',
                                                        lineHeight: '1.3'
                                                    }}>
                                                        {node.name}
                                                    </div>
                                                    <div style={{
                                                        fontSize: '10px',
                                                        color: '#868e96'
                                                    }}>
                                                        {node.task_type || 'Task'} • {getActivityStatus(node.progress_pct || 0)}
                                                        {isCritical && <span style={{ color: '#dc3545', marginLeft: '8px' }}>🔴 CRITICAL</span>}
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        {/* Task ID */}
                                        <div style={{
                                            fontSize: '12px',
                                            fontFamily: 'monospace',
                                            color: isProject ? '#667eea' :
                                                isWBS ? '#4a90e2' : '#6c757d'
                                        }}>
                                            {isProject ? 'PROJECT' :
                                                isWBS ? 'WBS' :
                                                    node.task_id}
                                        </div>

                                        {/* Duration */}
                                        <div style={{
                                            textAlign: 'center',
                                            fontWeight: (isProject || isWBS) ? '700' : '600',
                                            fontSize: '13px'
                                        }}>
                                            {node.duration_days ? `${Math.round(node.duration_days)}d` : '-'}
                                        </div>

                                        {/* Progress */}
                                        <div style={{ textAlign: 'center' }}>
                                            <div style={{
                                                fontSize: '12px',
                                                fontWeight: '600',
                                                color: (node.progress_pct || 0) >= 100 ? '#28a745' :
                                                    (node.progress_pct || 0) > 0 ? '#007bff' : '#6c757d'
                                            }}>
                                                {Math.round(node.progress_pct || 0)}%
                                            </div>
                                            {isActivity && (
                                                <div style={{
                                                    width: '100%',
                                                    height: '4px',
                                                    backgroundColor: '#e9ecef',
                                                    borderRadius: '2px',
                                                    marginTop: '2px',
                                                    overflow: 'hidden'
                                                }}>
                                                    <div style={{
                                                        width: `${node.progress_pct || 0}%`,
                                                        height: '100%',
                                                        backgroundColor: (node.progress_pct || 0) >= 100 ? '#28a745' :
                                                            (node.progress_pct || 0) > 0 ? '#007bff' : '#6c757d',
                                                        borderRadius: '2px'
                                                    }} />
                                                </div>
                                            )}
                                        </div>

                                        {/* Start Date */}
                                        <div style={{
                                            fontSize: '11px',
                                            fontFamily: 'monospace',
                                            color: '#495057',
                                            textAlign: 'center'
                                        }}>
                                            {formatDate(node.early_start_date || null)}
                                        </div>

                                        {/* End Date */}
                                        <div style={{
                                            fontSize: '11px',
                                            fontFamily: 'monospace',
                                            color: '#495057',
                                            textAlign: 'center'
                                        }}>
                                            {formatDate(node.early_end_date || null)}
                                        </div>

                                        {/* Actual Start */}
                                        <div style={{
                                            fontSize: '11px',
                                            fontFamily: 'monospace',
                                            color: node.actual_start_date ? '#28a745' : '#dee2e6',
                                            textAlign: 'center'
                                        }}>
                                            {formatDate(node.actual_start_date || null) || '-'}
                                        </div>

                                        {/* Actual End */}
                                        <div style={{
                                            fontSize: '11px',
                                            fontFamily: 'monospace',
                                            color: node.actual_end_date ? '#28a745' : '#dee2e6',
                                            textAlign: 'center'
                                        }}>
                                            {formatDate(node.actual_end_date || null) || '-'}
                                        </div>

                                        {/* Float */}
                                        <div style={{ textAlign: 'center' }}>
                                            {isActivity && (
                                                <span style={{
                                                    fontSize: '11px',
                                                    fontWeight: '700',
                                                    color: (node.total_float_days || 0) === 0 ? '#dc3545' :
                                                        (node.total_float_days || 0) <= 5 ? '#fd7e14' : '#28a745',
                                                    padding: '2px 6px',
                                                    borderRadius: '3px',
                                                    backgroundColor: (node.total_float_days || 0) === 0 ? '#ffebee' :
                                                        (node.total_float_days || 0) <= 5 ? '#fff3e0' : '#e8f5e8'
                                                }}>
                                                    {Math.round(node.total_float_days || 0)}d
                                                </span>
                                            )}
                                            {(isProject || isWBS) && (
                                                <span style={{
                                                    fontSize: '11px',
                                                    fontWeight: '600',
                                                    color: '#6c757d'
                                                }}>
                                                    {node.total_float_days !== undefined ? `${Math.round(node.total_float_days)}d` : '-'}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Status Bar */}
            <div style={{
                backgroundColor: '#f8f9fa',
                padding: '8px 20px',
                borderTop: '1px solid #dee2e6',
                fontSize: '12px',
                color: '#6c757d',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
            }}>
                <div>
                    Displaying {hierarchy.filter(h => h.type === 'activity').length} activities
                    in P6 hierarchy structure
                    {projectInfo && ` • Project: ${projectInfo.project_name}`}
                </div>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                    <span><span style={{ color: '#dc3545' }}>●</span> Critical (0 Float)</span>
                    <span><span style={{ color: '#fd7e14' }}>●</span> Near Critical (≤5)</span>
                    <span><span style={{ color: '#28a745' }}>●</span> Normal Float</span>
                    <span><span style={{ color: '#4a90e2' }}>●</span> WBS Structure</span>
                    <span><span style={{ color: '#667eea' }}>●</span> Project Level</span>
                </div>
            </div>
        </div>
    );
};

export default ActivitiesPage;