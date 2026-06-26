# To-Do List Application

A modern, fully-functional to-do list application with local storage persistence, priority management, and filtering capabilities.

## Features

✅ **Add Tasks** - Quickly add new tasks to your list
✅ **Edit Tasks** - Modify task descriptions and priorities
✅ **Priority Levels** - Organize tasks by Low, Medium, and High priority
✅ **Mark Complete** - Check off completed tasks
✅ **Delete Tasks** - Remove individual tasks
✅ **Filter View** - View All, Active, or Completed tasks
✅ **Local Storage** - All tasks are saved automatically to your browser
✅ **Statistics** - Track total, active, and completed tasks
✅ **Responsive Design** - Works perfectly on mobile and desktop
✅ **Keyboard Support** - Press Enter to add a task
✅ **Clear Completed** - Remove all completed tasks at once

## How to Use

1. **Add a Task**
   - Type your task in the input field
   - Click "Add" or press Enter

2. **Mark Complete**
   - Check the checkbox next to a task to mark it as completed

3. **Edit a Task**
   - Click the edit button (pencil icon) on any task
   - Modify the description and/or priority
   - Click "Save" to update

4. **Delete a Task**
   - Click the delete button (trash icon) on any task
   - Confirm the deletion

5. **Filter Tasks**
   - Click "All" to see all tasks
   - Click "Active" to see incomplete tasks only
   - Click "Completed" to see finished tasks only

6. **Clear Completed**
   - Click "Clear Completed" at the bottom to remove all finished tasks

## Technical Details

### Local Storage Implementation
- Tasks are automatically saved to browser's localStorage under the key `todos_app`
- JSON format ensures data integrity
- Automatic error handling for storage issues

### Data Structure
```javascript
{
  id: timestamp,
  text: "Task description",
  completed: boolean,
  priority: "low" | "medium" | "high",
  createdAt: ISO timestamp
}
```

### Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Mobile browsers: ✅ Full support

## Storage Limits
- Most browsers support 5-10MB of localStorage
- Current app uses minimal space (~5KB per 100 tasks)

## Privacy
- All data is stored locally in your browser
- No data is sent to any server
- Clearing browser data will clear your tasks

## Future Enhancements
- Cloud sync functionality
- Due dates and reminders
- Task categories/tags
- Dark mode theme
- Export/Import functionality
- Recurring tasks

## License
Free to use and modify
