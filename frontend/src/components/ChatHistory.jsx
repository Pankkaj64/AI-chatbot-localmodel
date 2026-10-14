import React, { useState, useEffect } from "react";


/**
 * A React component that displays a list of recent chats and allows the user to select a chat to view.
 *
 * @param {function} onSelectChat - A function that is called when the user selects a chat.
 * @param {string} currentSessionId - The ID of the currently active chat session.
 * @param {function} onNewChat - A function that starts a new chat (called when the active chat is deleted).
 */
export default function ChatHistory({ onSelectChat, currentSessionId, onNewChat }) {
  const [sessions, setSessions] = useState([]);
  const [search, setSearch] = useState(""); // Initialize with "" instead of null

/**
 * Fetches the list of recent chats from the backend and updates the state with the new list.
 * If the fetch fails, logs an error message to the console.
 */
  const refreshHistory = () => {
    fetch("http://localhost:8000/chat/sessions")
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setSessions(data);
        }
      })
      .catch(err => console.error("Failed to fetch sessions:", err));
  };

  useEffect(() => {
    refreshHistory();
    setSearch(''); 
  }, [currentSessionId]);

  // Filter the sessions based on the search term
  const filtered = sessions.filter(s => 
    (s.title || "").toLowerCase().includes(search.toLowerCase())
  );

  // function for deleting the chathistory
  const deleteChat = async (e, sessionId) => {
    e.stopPropagation(); // Prevent selecting the chat when clicking delete
    if (!window.confirm("Are you sure you want to delete this chat?")) return;

    try {
      const res = await fetch(`http://localhost:8000/chat/sessions/${sessionId}`, {
        method: 'DELETE',
      });

      if (res.ok) {
        // Refresh the list after deletion
        refreshHistory(); 
      
        // If the deleted chat was the active one, start a new chat
        if (sessionId === currentSessionId) {
          onNewChat();
        } 
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };
  
  return (
    <div className="history">
      <div className="search-container" style={{ 
        padding: '12px',
        alignContent: 'center',
        marginRight: '12px',
        marginLeft: '-5px'
        }}>
        <input 
          type="text"
          placeholder="Search chats..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="history-search-input"
          style={{
            width: '100%',
            background: '#2a2a2a',
            border: '1px solid #444',
            color: 'white',
            borderRadius: '5px',
            padding: '8px',
          }}
        />
      </div>

      <p style={{ 
        color: '#666', 
        fontSize: '12px', 
        paddingLeft: '10px' 
      }}>Recent Chats</p>
      
      <div className="history-list-container">
        {filtered.map((s) => (
          <div
            key={s.session_id}
            className={`history-item ${currentSessionId === s.session_id ? 'active' : ''}`}
            onClick={() => onSelectChat(s.session_id)}
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
              <span className="chat-icon">💬</span>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {s.title || "Untitled Chat"}
              </span>
            </div>
            <button 
              className="delete-chat-btn" 
              onClick={(e) => deleteChat(e, s.session_id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}
            >
              🗑️
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}