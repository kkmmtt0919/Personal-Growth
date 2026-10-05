export const taskAnchor = (id: string) => `task-${id}`
export const taskHref = (goalId: string, taskId: string) => `/growth/${encodeURIComponent(goalId)}#${encodeURIComponent(taskAnchor(taskId))}`
