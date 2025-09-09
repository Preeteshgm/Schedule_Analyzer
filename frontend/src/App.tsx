import React, { useEffect, useState } from 'react'
import EnhancedActivitiesPage from './EnhancedActivitiesPage'
import GanttChart from './GanttChart'

interface Project {
    id: number
    name: string
    description: string
    created_date: string
    created_by: string
    status: string
    schedule_count: number
}

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

function App() {
    const [currentView, setCurrentView] = useState<'projects' | 'schedules' | 'activities' | 'gantt'>('projects')
    const [selectedProject, setSelectedProject] = useState<Project | null>(null)
    const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null)

    // Debug states
    const [debugInfo, setDebugInfo] = useState<string>('')
    const [apiStatus, setApiStatus] = useState<'testing' | 'success' | 'error'>('testing')

    // Projects state
    const [projects, setProjects] = useState<Project[]>([])
    const [loadingProjects, setLoadingProjects] = useState(true)
    const [creatingProject, setCreatingProject] = useState(false)
    const [showProjectForm, setShowProjectForm] = useState(false)
    const [newProject, setNewProject] = useState({ name: '', description: '' })

    // Schedules state  
    const [schedules, setSchedules] = useState<Schedule[]>([])
    const [loadingSchedules, setLoadingSchedules] = useState(false)
    const [creatingSchedule, setCreatingSchedule] = useState(false)
    const [showScheduleForm, setShowScheduleForm] = useState(false)
    const [newSchedule, setNewSchedule] = useState({ name: '', description: '' })

    // File upload state
    const [showFileUpload, setShowFileUpload] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [uploadProgress, setUploadProgress] = useState(0)
    const [uploading, setUploading] = useState(false)
    const [uploadScheduleName, setUploadScheduleName] = useState('')

    // Debug function to test API
    const testAPI = async () => {
        try {
            setDebugInfo('Testing API connection...')

            // Test health endpoint
            const healthResponse = await fetch('http://localhost:5000/api/health')
            const healthData = await healthResponse.json()

            setDebugInfo(`Health check: ${healthData.message}`)

            // Test debug endpoint
            const debugResponse = await fetch('http://localhost:5000/api/debug')
            const debugData = await debugResponse.json()

            setDebugInfo(`Database: ${debugData.status}, Projects: ${debugData.project_count}`)
            setApiStatus('success')

        } catch (error) {
            console.error('API test failed:', error)
            setDebugInfo(`API Error: ${error}`)
            setApiStatus('error')
        }
    }

    // Project functions
    const fetchProjects = async () => {
        try {
            setDebugInfo('Fetching projects...')
            const response = await fetch('http://localhost:5000/api/projects')

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`)
            }

            const data = await response.json()
            setProjects(data)
            setLoadingProjects(false)
            setDebugInfo(`Loaded ${data.length} projects successfully`)
            setApiStatus('success')
        } catch (error) {
            console.error('Error fetching projects:', error)
            setLoadingProjects(false)
            setDebugInfo(`Fetch Error: ${error}`)
            setApiStatus('error')
        }
    }

    const createProject = async () => {
        if (!newProject.name.trim()) {
            alert('Project name is required!')
            return
        }

        setCreatingProject(true)
        try {
            const response = await fetch('http://localhost:5000/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: newProject.name,
                    description: newProject.description,
                    created_by: 'frontend_user'
                })
            })

            if (response.ok) {
                setNewProject({ name: '', description: '' })
                setShowProjectForm(false)
                fetchProjects()
                setDebugInfo('Project created successfully!')
            } else {
                const errorData = await response.json()
                alert(`Error creating project: ${errorData.error}`)
            }
        } catch (error) {
            console.error('Error creating project:', error)
            alert('Error creating project')
            setDebugInfo(`Create Error: ${error}`)
        }
        setCreatingProject(false)
    }

    // Schedule functions
    const fetchSchedules = async (projectId: number) => {
        setLoadingSchedules(true)
        try {
            const response = await fetch(`http://localhost:5000/api/projects/${projectId}/schedules`)
            const data = await response.json()
            setSchedules(data)
            setLoadingSchedules(false)
            setDebugInfo(`Loaded ${data.length} schedules for project ${projectId}`)
        } catch (error) {
            console.error('Error fetching schedules:', error)
            setLoadingSchedules(false)
            setDebugInfo(`Schedule fetch error: ${error}`)
        }
    }

    const createSchedule = async () => {
        if (!newSchedule.name.trim() || !selectedProject) {
            alert('Schedule name is required!')
            return
        }

        setCreatingSchedule(true)
        try {
            const response = await fetch(`http://localhost:5000/api/projects/${selectedProject.id}/schedules`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: newSchedule.name,
                    description: newSchedule.description,
                    created_by: 'frontend_user'
                })
            })

            if (response.ok) {
                setNewSchedule({ name: '', description: '' })
                setShowScheduleForm(false)
                fetchSchedules(selectedProject.id)
            } else {
                alert('Error creating schedule')
            }
        } catch (error) {
            console.error('Error creating schedule:', error)
            alert('Error creating schedule')
        }
        setCreatingSchedule(false)
    }

    // File upload functions
    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (file) {
            if (!file.name.toLowerCase().endsWith('.xer')) {
                alert('Please select a .xer file')
                return
            }

            if (file.size > 100 * 1024 * 1024) { // 100MB
                alert('File size must be less than 100MB')
                return
            }

            setSelectedFile(file)
            // Auto-generate schedule name from filename
            const baseName = file.name.replace('.xer', '').replace(/[_-]/g, ' ')
            setUploadScheduleName(baseName)
        }
    }

    const uploadXerFile = async () => {
        if (!selectedFile || !selectedProject || !uploadScheduleName.trim()) {
            alert('Please select a file and enter a schedule name')
            return
        }

        setUploading(true)
        setUploadProgress(0)

        try {
            const formData = new FormData()
            formData.append('file', selectedFile)
            formData.append('schedule_name', uploadScheduleName)
            formData.append('description', `Imported from ${selectedFile.name}`)
            formData.append('created_by', 'file_upload')

            // Simulate upload progress
            const progressInterval = setInterval(() => {
                setUploadProgress(prev => Math.min(prev + 10, 90))
            }, 200)

            const response = await fetch(`http://localhost:5000/api/projects/${selectedProject.id}/upload-xer`, {
                method: 'POST',
                body: formData
            })

            clearInterval(progressInterval)
            setUploadProgress(100)

            if (response.ok) {
                const result = await response.json()

                // Reset form
                setSelectedFile(null)
                setUploadScheduleName('')
                setShowFileUpload(false)
                setUploadProgress(0)

                // Refresh schedules list
                fetchSchedules(selectedProject.id)

                alert(`File uploaded successfully! Schedule "${result.schedule.name}" created.`)
            } else {
                const error = await response.json()
                alert(`Upload failed: ${error.error}`)
            }
        } catch (error) {
            console.error('Upload error:', error)
            alert('Upload failed. Please try again.')
        }

        setUploading(false)
        setUploadProgress(0)
    }

    const deleteSchedule = async (scheduleId: number) => {
        if (!confirm('Are you sure you want to delete this schedule? This cannot be undone.')) {
            return
        }

        try {
            const response = await fetch(`http://localhost:5000/api/schedules/${scheduleId}/delete`, {
                method: 'DELETE'
            })

            if (response.ok) {
                if (selectedProject) {
                    fetchSchedules(selectedProject.id)
                }
            } else {
                alert('Error deleting schedule')
            }
        } catch (error) {
            console.error('Error deleting schedule:', error)
            alert('Error deleting schedule')
        }
    }

    const viewProjectSchedules = (project: Project) => {
        setSelectedProject(project)
        setCurrentView('schedules')
        fetchSchedules(project.id)
    }

    const viewScheduleActivities = (schedule: Schedule) => {
        console.log('Viewing activities for schedule:', schedule)
        setSelectedSchedule(schedule)
        setCurrentView('activities')
    }

    const viewScheduleGantt = (schedule: Schedule) => {
        console.log('Viewing Gantt chart for schedule:', schedule)
        setSelectedSchedule(schedule)
        setCurrentView('gantt')
    }

    const backToProjects = () => {
        setCurrentView('projects')
        setSelectedProject(null)
        setSelectedSchedule(null)
        setSchedules([])
        setShowScheduleForm(false)
        setShowFileUpload(false)
        setSelectedFile(null)
        setUploadScheduleName('')
    }

    const backToSchedules = () => {
        setCurrentView('schedules')
        setSelectedSchedule(null)
        if (selectedProject) {
            fetchSchedules(selectedProject.id)
        }
    }

    const formatFileSize = (bytes: number) => {
        if (bytes === 0) return '0 Bytes'
        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    useEffect(() => {
        // Test API connection first, then fetch projects
        testAPI().then(() => {
            fetchProjects()
        })
    }, [])

    // Debug useEffect
    useEffect(() => {
        console.log('Current view:', currentView)
        console.log('Selected schedule:', selectedSchedule)
    }, [currentView, selectedSchedule])

    // Loading state
    if (loadingProjects) {
        return (
            <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
                <h1>📊 Schedule Foundation App</h1>

                {/* Debug Info */}
                <div style={{
                    backgroundColor: apiStatus === 'error' ? '#ffebee' : '#e3f2fd',
                    padding: '15px',
                    borderRadius: '5px',
                    marginBottom: '20px',
                    border: `1px solid ${apiStatus === 'error' ? '#ffcdd2' : '#bbdefb'}`
                }}>
                    <h4>🔧 Connection Status</h4>
                    <p><strong>Status:</strong> {apiStatus}</p>
                    <p><strong>Info:</strong> {debugInfo}</p>
                    <button
                        onClick={testAPI}
                        style={{ padding: '5px 10px', backgroundColor: '#2196f3', color: 'white', border: 'none', borderRadius: '3px' }}
                    >
                        🔄 Test API Again
                    </button>
                </div>

                <div>Loading projects...</div>
            </div>
        )
    }

    return (
        <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
            {/* Header */}
            <div style={{ borderBottom: '1px solid #ddd', paddingBottom: '20px', marginBottom: '20px' }}>
                <h1 style={{ margin: 0 }}>📊 Schedule Foundation App</h1>

                {/* Debug Info */}
                {debugInfo && (
                    <div style={{
                        backgroundColor: apiStatus === 'error' ? '#ffebee' : '#e8f5e8',
                        padding: '10px',
                        borderRadius: '5px',
                        marginTop: '10px',
                        fontSize: '14px',
                        border: `1px solid ${apiStatus === 'error' ? '#ffcdd2' : '#c8e6c9'}`
                    }}>
                        <strong>Status:</strong> {debugInfo}
                    </div>
                )}

                {/* Breadcrumb */}
                <div style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                    {currentView === 'projects' ? (
                        <span>Projects</span>
                    ) : currentView === 'schedules' ? (
                        <span>
                            <a href="#" onClick={backToProjects} style={{ color: '#007bff', textDecoration: 'none' }}>
                                Projects
                            </a>
                            {' > '}
                            <span>{selectedProject?.name} - Schedules</span>
                        </span>
                    ) : (
                        <span>
                            <a href="#" onClick={backToProjects} style={{ color: '#007bff', textDecoration: 'none' }}>
                                Projects
                            </a>
                            {' > '}
                            <a href="#" onClick={backToSchedules} style={{ color: '#007bff', textDecoration: 'none' }}>
                                {selectedProject?.name} - Schedules
                            </a>
                            {' > '}
                            <span>{selectedSchedule?.name} - {currentView === 'activities' ? 'Activities' : 'Gantt Chart'}</span>
                        </span>
                    )}
                </div>
            </div>

            {/* Projects View */}
            {currentView === 'projects' && (
                <>
                    <div style={{ marginBottom: '20px' }}>
                        <button
                            onClick={() => setShowProjectForm(!showProjectForm)}
                            style={{
                                padding: '10px 20px',
                                backgroundColor: '#007bff',
                                color: 'white',
                                border: 'none',
                                borderRadius: '5px',
                                cursor: 'pointer',
                                marginRight: '10px'
                            }}
                        >
                            {showProjectForm ? 'Cancel' : '+ New Project'}
                        </button>

                        <button
                            onClick={testAPI}
                            style={{
                                padding: '10px 20px',
                                backgroundColor: '#17a2b8',
                                color: 'white',
                                border: 'none',
                                borderRadius: '5px',
                                cursor: 'pointer'
                            }}
                        >
                            🔧 Test API
                        </button>
                    </div>

                    {showProjectForm && (
                        <div style={{
                            border: '1px solid #ddd',
                            padding: '20px',
                            borderRadius: '5px',
                            backgroundColor: '#f9f9f9',
                            marginBottom: '20px'
                        }}>
                            <h3>Create New Project</h3>
                            <div style={{ marginBottom: '10px' }}>
                                <input
                                    type="text"
                                    placeholder="Project Name *"
                                    value={newProject.name}
                                    onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                                    style={{
                                        width: '100%',
                                        padding: '8px',
                                        border: '1px solid #ddd',
                                        borderRadius: '3px'
                                    }}
                                />
                            </div>
                            <div style={{ marginBottom: '10px' }}>
                                <textarea
                                    placeholder="Description (optional)"
                                    value={newProject.description}
                                    onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                                    style={{
                                        width: '100%',
                                        padding: '8px',
                                        border: '1px solid #ddd',
                                        borderRadius: '3px',
                                        height: '60px'
                                    }}
                                />
                            </div>
                            <button
                                onClick={createProject}
                                disabled={creatingProject}
                                style={{
                                    padding: '8px 16px',
                                    backgroundColor: '#28a745',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '3px',
                                    cursor: creatingProject ? 'not-allowed' : 'pointer'
                                }}
                            >
                                {creatingProject ? 'Creating...' : 'Create Project'}
                            </button>
                        </div>
                    )}

                    <h2>Projects ({projects.length})</h2>

                    {projects.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', backgroundColor: '#f8f9fa', borderRadius: '5px' }}>
                            <p style={{ marginBottom: '15px' }}>No projects found.</p>
                            <p style={{ color: '#666', fontSize: '14px' }}>
                                Create your first project above! If you're seeing this after the API test passed, there might be a database sync issue.
                            </p>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gap: '10px' }}>
                            {projects.map((project) => (
                                <div key={project.id} style={{
                                    border: '1px solid #ddd',
                                    padding: '15px',
                                    borderRadius: '5px',
                                    backgroundColor: 'white'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div style={{ flex: 1 }}>
                                            <h3 style={{ margin: '0 0 5px 0' }}>{project.name}</h3>
                                            <p style={{ margin: '0 0 5px 0', color: '#666' }}>{project.description}</p>
                                            <small style={{ color: '#999' }}>
                                                Created: {new Date(project.created_date).toLocaleDateString()} by {project.created_by}
                                                {' • '}
                                                {project.schedule_count} schedule{project.schedule_count !== 1 ? 's' : ''}
                                            </small>
                                        </div>
                                        <button
                                            onClick={() => viewProjectSchedules(project)}
                                            style={{
                                                padding: '5px 10px',
                                                backgroundColor: '#17a2b8',
                                                color: 'white',
                                                border: 'none',
                                                borderRadius: '3px',
                                                cursor: 'pointer',
                                                marginLeft: '10px'
                                            }}
                                        >
                                            View Schedules →
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}

            {/* Schedules View - Enhanced with File Upload */}
            {currentView === 'schedules' && selectedProject && (
                <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h2>Schedules for {selectedProject.name}</h2>
                        <button
                            onClick={backToProjects}
                            style={{
                                padding: '10px 20px',
                                backgroundColor: '#6c757d',
                                color: 'white',
                                border: 'none',
                                borderRadius: '5px',
                                cursor: 'pointer'
                            }}
                        >
                            ← Back to Projects
                        </button>
                    </div>

                    {/* Action Buttons */}
                    <div style={{ marginBottom: '20px' }}>
                        <button
                            onClick={() => setShowFileUpload(!showFileUpload)}
                            style={{
                                padding: '10px 20px',
                                backgroundColor: '#28a745',
                                color: 'white',
                                border: 'none',
                                borderRadius: '5px',
                                cursor: 'pointer',
                                marginRight: '10px'
                            }}
                        >
                            {showFileUpload ? 'Cancel Upload' : '📁 Upload XER File'}
                        </button>

                        <button
                            onClick={() => setShowScheduleForm(!showScheduleForm)}
                            style={{
                                padding: '10px 20px',
                                backgroundColor: '#007bff',
                                color: 'white',
                                border: 'none',
                                borderRadius: '5px',
                                cursor: 'pointer'
                            }}
                        >
                            {showScheduleForm ? 'Cancel' : '+ Create Empty Schedule'}
                        </button>
                    </div>

                    {/* File Upload Form */}
                    {showFileUpload && (
                        <div style={{
                            border: '2px dashed #007bff',
                            padding: '30px',
                            borderRadius: '10px',
                            backgroundColor: '#f8f9ff',
                            marginBottom: '20px',
                            textAlign: 'center'
                        }}>
                            <h3>📁 Upload Primavera P6 XER File</h3>
                            <p style={{ color: '#666', marginBottom: '20px' }}>
                                Select a .xer file to import project schedule data
                            </p>

                            <input
                                type="file"
                                onChange={handleFileSelect}
                                accept=".xer"
                                style={{
                                    marginBottom: '15px',
                                    padding: '10px',
                                    border: '1px solid #ddd',
                                    borderRadius: '5px',
                                    width: '300px'
                                }}
                            />

                            {selectedFile && (
                                <div style={{
                                    backgroundColor: 'white',
                                    padding: '15px',
                                    borderRadius: '5px',
                                    margin: '15px 0',
                                    border: '1px solid #ddd'
                                }}>
                                    <h4>📄 File Selected:</h4>
                                    <p><strong>Name:</strong> {selectedFile.name}</p>
                                    <p><strong>Size:</strong> {formatFileSize(selectedFile.size)}</p>

                                    <div style={{ marginTop: '15px' }}>
                                        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                                            Schedule Name:
                                        </label>
                                        <input
                                            type="text"
                                            value={uploadScheduleName}
                                            onChange={(e) => setUploadScheduleName(e.target.value)}
                                            placeholder="Enter schedule name"
                                            style={{
                                                width: '300px',
                                                padding: '8px',
                                                border: '1px solid #ddd',
                                                borderRadius: '3px',
                                                marginBottom: '15px'
                                            }}
                                        />
                                    </div>

                                    {uploading && (
                                        <div style={{ margin: '15px 0' }}>
                                            <div style={{
                                                width: '100%',
                                                height: '20px',
                                                backgroundColor: '#e9ecef',
                                                borderRadius: '10px',
                                                overflow: 'hidden',
                                                marginBottom: '10px'
                                            }}>
                                                <div style={{
                                                    width: `${uploadProgress}%`,
                                                    height: '100%',
                                                    backgroundColor: '#28a745',
                                                    transition: 'width 0.3s ease'
                                                }}></div>
                                            </div>
                                            <p>Uploading and parsing... {uploadProgress}%</p>
                                        </div>
                                    )}

                                    <button
                                        onClick={uploadXerFile}
                                        disabled={uploading || !uploadScheduleName.trim()}
                                        style={{
                                            padding: '10px 20px',
                                            backgroundColor: uploading ? '#6c757d' : '#28a745',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '5px',
                                            cursor: uploading ? 'not-allowed' : 'pointer',
                                            marginRight: '10px'
                                        }}
                                    >
                                        {uploading ? '⏳ Processing...' : '🚀 Upload & Parse'}
                                    </button>

                                    <button
                                        onClick={() => {
                                            setSelectedFile(null)
                                            setUploadScheduleName('')
                                        }}
                                        disabled={uploading}
                                        style={{
                                            padding: '10px 20px',
                                            backgroundColor: '#6c757d',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '5px',
                                            cursor: uploading ? 'not-allowed' : 'pointer'
                                        }}
                                    >
                                        Clear
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Manual Schedule Creation Form */}
                    {showScheduleForm && (
                        <div style={{
                            border: '1px solid #ddd',
                            padding: '20px',
                            borderRadius: '5px',
                            backgroundColor: '#f9f9f9',
                            marginBottom: '20px'
                        }}>
                            <h3>Create Empty Schedule</h3>
                            <div style={{ marginBottom: '10px' }}>
                                <input
                                    type="text"
                                    placeholder="Schedule Name *"
                                    value={newSchedule.name}
                                    onChange={(e) => setNewSchedule({ ...newSchedule, name: e.target.value })}
                                    style={{
                                        width: '100%',
                                        padding: '8px',
                                        border: '1px solid #ddd',
                                        borderRadius: '3px'
                                    }}
                                />
                            </div>
                            <div style={{ marginBottom: '10px' }}>
                                <textarea
                                    placeholder="Description (optional)"
                                    value={newSchedule.description}
                                    onChange={(e) => setNewSchedule({ ...newSchedule, description: e.target.value })}
                                    style={{
                                        width: '100%',
                                        padding: '8px',
                                        border: '1px solid #ddd',
                                        borderRadius: '3px',
                                        height: '60px'
                                    }}
                                />
                            </div>
                            <button
                                onClick={createSchedule}
                                disabled={creatingSchedule}
                                style={{
                                    padding: '8px 16px',
                                    backgroundColor: '#007bff',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '3px',
                                    cursor: creatingSchedule ? 'not-allowed' : 'pointer'
                                }}
                            >
                                {creatingSchedule ? 'Creating...' : 'Create Schedule'}
                            </button>
                        </div>
                    )}

                    {/* Schedules List */}
                    <h3>Schedules ({schedules.length})</h3>

                    {loadingSchedules ? (
                        <div style={{ textAlign: 'center', padding: '20px' }}>
                            Loading schedules...
                        </div>
                    ) : schedules.length === 0 ? (
                        <div style={{
                            textAlign: 'center',
                            padding: '40px',
                            backgroundColor: '#f8f9fa',
                            borderRadius: '5px',
                            border: '1px dashed #ddd'
                        }}>
                            <p style={{ marginBottom: '15px' }}>📋 No schedules found for this project.</p>
                            <p style={{ color: '#666', fontSize: '14px' }}>
                                Upload an XER file or create an empty schedule to get started.
                            </p>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gap: '15px' }}>
                            {schedules.map((schedule) => (
                                <div key={schedule.id} style={{
                                    border: '1px solid #ddd',
                                    padding: '20px',
                                    borderRadius: '8px',
                                    backgroundColor: 'white'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div style={{ flex: 1 }}>
                                            <h4 style={{ margin: '0 0 10px 0', color: '#2c3e50' }}>
                                                📊 {schedule.name}
                                            </h4>

                                            {schedule.description && (
                                                <p style={{ margin: '0 0 10px 0', color: '#666' }}>
                                                    {schedule.description}
                                                </p>
                                            )}

                                            <div style={{
                                                display: 'grid',
                                                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                                                gap: '10px',
                                                marginBottom: '10px'
                                            }}>
                                                <div>
                                                    <strong>📋 Activities:</strong> {schedule.total_activities.toLocaleString()}
                                                </div>
                                                <div>
                                                    <strong>🔗 Relationships:</strong> {schedule.total_relationships.toLocaleString()}
                                                </div>
                                                <div>
                                                    <strong>📅 Status:</strong>
                                                    <span style={{
                                                        marginLeft: '5px',
                                                        padding: '2px 6px',
                                                        borderRadius: '3px',
                                                        fontSize: '12px',
                                                        backgroundColor: schedule.status === 'parsed' ? '#d4edda' :
                                                            schedule.status === 'error' ? '#f8d7da' : '#fff3cd',
                                                        color: schedule.status === 'parsed' ? '#155724' :
                                                            schedule.status === 'error' ? '#721c24' : '#856404'
                                                    }}>
                                                        {schedule.status.toUpperCase()}
                                                    </span>
                                                </div>
                                            </div>

                                            {schedule.file_name && (
                                                <div style={{ fontSize: '14px', color: '#666', marginBottom: '5px' }}>
                                                    📁 Source: {schedule.file_name} ({formatFileSize(schedule.file_size || 0)})
                                                </div>
                                            )}

                                            <div style={{ fontSize: '12px', color: '#999' }}>
                                                Created: {new Date(schedule.created_date).toLocaleDateString()} by {schedule.created_by}
                                                {schedule.data_date && (
                                                    <span> • Data Date: {new Date(schedule.data_date).toLocaleDateString()}</span>
                                                )}
                                            </div>
                                        </div>

                                        <div style={{ marginLeft: '15px' }}>
                                            {schedule.status === 'parsed' && schedule.total_activities > 0 && (
                                                <>
                                                    <button
                                                        onClick={() => {
                                                            console.log('View Activities button clicked! Schedule:', schedule)
                                                            viewScheduleActivities(schedule)
                                                        }}
                                                        style={{
                                                            padding: '8px 12px',
                                                            backgroundColor: '#007bff',
                                                            color: 'white',
                                                            border: 'none',
                                                            borderRadius: '3px',
                                                            cursor: 'pointer',
                                                            marginBottom: '5px',
                                                            display: 'block',
                                                            width: '100%'
                                                        }}
                                                    >
                                                        📊 View Activities
                                                    </button>

                                                    <button
                                                        onClick={() => {
                                                            console.log('View Gantt button clicked! Schedule:', schedule)
                                                            viewScheduleGantt(schedule)
                                                        }}
                                                        style={{
                                                            padding: '8px 12px',
                                                            backgroundColor: '#28a745',
                                                            color: 'white',
                                                            border: 'none',
                                                            borderRadius: '3px',
                                                            cursor: 'pointer',
                                                            marginBottom: '5px',
                                                            display: 'block',
                                                            width: '100%'
                                                        }}
                                                    >
                                                        📈 Gantt Chart
                                                    </button>
                                                </>
                                            )}

                                            <button
                                                onClick={() => deleteSchedule(schedule.id)}
                                                style={{
                                                    padding: '8px 12px',
                                                    backgroundColor: '#dc3545',
                                                    color: 'white',
                                                    border: 'none',
                                                    borderRadius: '3px',
                                                    cursor: 'pointer',
                                                    display: 'block',
                                                    width: '100%'
                                                }}
                                            >
                                                🗑️ Delete
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}

            {/* Activities View - Enhanced Activities Page */}
            {currentView === 'activities' && selectedSchedule && (
                <EnhancedActivitiesPage
                    schedule={selectedSchedule}
                    onBackToSchedules={backToSchedules}
                />
            )}

            {/* Gantt Chart View - NEW */}
            {currentView === 'gantt' && selectedSchedule && (
                <GanttChart
                    schedule={selectedSchedule}
                    onBackToSchedules={backToSchedules}
                />
            )}
        </div>
    )
}

export default App