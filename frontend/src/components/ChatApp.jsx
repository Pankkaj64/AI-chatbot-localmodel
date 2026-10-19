import React, { useRef, useState, useEffect } from "react";
import ChatHistory from "./ChatHistory";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import ModelSelector from "./ModelSelector";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "../App.css";
import ProjectSelector from "./ProjectSelector";

/**
 * ChatApp is the main React component for the chat application.
 * It manages the chat history, current session, and user preferences.
 * It also handles sending messages, generating images, and loading sessions.
 * 
 * @prop {string} message - The current user input message.
 * @prop {File | null} image - The current user input image, or null if no image is selected.
 * @prop {bool} generateImg - Whether the AI should generate an image based on the user's input message.
 * @prop {string | null} error - Any error messages that should be displayed to the user.
 * @prop {bool} isSidebarOpen - Whether the sidebar should be displayed or not.

 * @prop {string} selectedModel - The currently selected model for generating responses.
 * @prop {string | null} currentSessionId - The ID of the current session, or null if no session is active.
 * @prop {number} currentSessionCost - The estimated cost of the current session in USD, or 0 if no session is active.
 * 
 * @function startNewChat - Resets the chat history and current session.
 * @function loadSession - Loads a session from the database and updates the chat history.
 * @function sendMessage - Sends a message to the AI and updates the chat history.
 */

function formatApiError(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";

        return [field, item.msg].filter(Boolean).join(".");
      })
      .join(".");
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return "The request failed. check the backend terminal for this";
}

export default function ChatApp() {
  const [message, setMessage] = useState("");
  const [images, setImages] = useState([]);
  const [generateImg, setGenerateImg] = useState(false);
  const [error, setError] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [imagePreviewUrls, setImagePreviewUrls] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const canSend = Boolean(message.trim() || images.length > 0) && !isSending;
  const [selectedProject, setSelectedProject] = useState(
    localStorage.getItem("selectedProject") || "",
  );
  const [selectedModel, setSelectedModel] = useState(() => {
    return localStorage.getItem("preferredModel") || "gemma3";
  });
  // Chat History
  const [chat, setChat] = useState(() => {
    const savedChat = localStorage.getItem("chatHistory");
    return savedChat ? JSON.parse(savedChat) : [];
  });
  // Current Session
  const [currentSessionId, setCurrentSessionId] = useState(() => {
    return localStorage.getItem("currentSessionId") || null;
  });

  const fileInputRef = useRef(null);
  const bottomRef = useRef(null);

  // On Mount: Load specific session if it exists
  useEffect(() => {
    const savedId = localStorage.getItem("currentSessionId");
    if (savedId) {
      loadSession(savedId);
    }
  }, []);

  // On Change: Sync with LocalStorage
  useEffect(() => {
    localStorage.setItem("chatHistory", JSON.stringify(chat));
    if (currentSessionId) {
      localStorage.setItem("currentSessionId", currentSessionId);
    } else {
      localStorage.removeItem("currentSessionId");
    }
  }, [chat, currentSessionId]);

  // UI: Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  // save preference when it changes
  useEffect(() => {
    localStorage.setItem("preferredModel", selectedModel);
  }, [selectedModel]);

  useEffect(() => {
    const urls = images.map((file) => URL.createObjectURL(file));
    setImagePreviewUrls(urls);

    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [images]);

  const addImages = (files) => {
    const selected = Array.from(files ?? []);
    const imageFiles = selected.filter((file) =>
      file.type.startsWith("image/"),
    );

    if (imageFiles.length !== selected.length) {
      setError("Please select image files only.");
    }

    if (imageFiles.length) {
      setImages((current) => [...current, ...imageFiles]);
    }
  };

  // Logic: Calculate current session cost dynamically from the chat history
  const currentSessionCost = chat.reduce((acc, msg) => {
    return acc + (msg.usage?.estimated_cost_usd || 0);
  }, 0);

  // ACTIONS
  const startNewChat = () => {
    setChat([]);
    setCurrentSessionId(null);
    setMessage("");
    setImages([]);
    localStorage.removeItem("chatHistory");
    localStorage.removeItem("currentSessionId");
  };

  // Load Session
  const loadSession = async (sessionId) => {
    try {
      const res = await fetch(
        `http://localhost:8000/chat/history/${sessionId}`,
      );
      const data = await res.json();

      if (Array.isArray(data)) {
        const formatted = data.map((m) => ({
          ...m,
          role: m.role === "assistant" ? "bot" : "user",
          text: m.text,
          image: m.image,
          usage: m.usage, // Usage retrieved from DB
        }));
        setChat(formatted);
        setCurrentSessionId(sessionId);
      }
    } catch (err) {
      console.error("Load Session Error:", err);
    }
  };

  // Send Message
  const sendMessage = async () => {
  const promptToSend = message;
  if (isSending || (!promptToSend.trim() && images.length === 0)) return;

  setError(null);
  setMessage("");

  const userMsg = {
    role: "user",
    text: promptToSend,
    images: images.map((file) => URL.createObjectURL(file)),
  };

  setChat((prev) => [
    ...prev,
    userMsg,
    { role: "bot", text: "Analyzing..." },
  ]);

  const formData = new FormData();
  formData.append("message", promptToSend);
  formData.append("model", selectedModel);
  formData.append("generate_img", String(generateImg));
  formData.append("project_name", selectedProject);

  images.forEach((file) => formData.append("images", file));

  if (currentSessionId) {
    formData.append("session_id", currentSessionId);
  }

  setIsSending(true);

  try {
    const res = await fetch("http://localhost:8000/chat/chat", {
      method: "POST",
      body: formData,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      setError(formatApiError(data.detail));
      setMessage((current) => current || promptToSend);
      setChat((prev) => prev.slice(0, -1));
      return;
    }

    if (!currentSessionId) {
      setCurrentSessionId(data.session_id);
    }

    setChat((prev) => [
      ...prev.slice(0, -1),
      {
        role: "bot",
        text: data.reply,
        images: data.image_urls ?? (data.image_url ? [data.image_url] : []),
        usage: data.usage,
      },
    ]);

    setImages([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setGenerateImg(false);
  } catch (err) {
    setError("Could not connect to the backend.");
    setMessage((current) => current || promptToSend);
    setChat((prev) => prev.slice(0, -1));
  } finally {
    setIsSending(false);
  }
};

  const handlePaste = (e) => {
    const blobs = Array.from(e.clipboardData?.items ?? [])
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);

    if (!blobs.length) return;

    e.preventDefault();

    const pastedFiles = blobs.map((blob, index) => {
      const type = blob.type || "image/png";
      const extension = type.split("/")[1]?.replace("jpeg", "jpg") || "png";

      return new File(
        [blob],
        `pasted-image-${Date.now()}-${index}.${extension}`,
        { type },
      );
    });

    addImages(pastedFiles);
  };

  const handleProjectChange = (projectName) => {
    if (selectedProject && selectedProject !== projectName) {
      startNewChat();
    }
    localStorage.setItem("selectedProject", projectName);
    setSelectedProject(projectName);
  };

  return (
    <div className="app-container">
      {error && (
        <div className="safety-alert" onClick={() => setError(null)}>
          ⚠️ {error}
        </div>
      )}

      <div className={`sidebar ${isSidebarOpen ? "open" : ""}`}>
        <button className="close-menu" onClick={() => setIsSidebarOpen(false)}>
          ✕
        </button>
        <button
          className="new-chat-btn"
          onClick={() => {
            startNewChat();
            setIsSidebarOpen(false);
          }}
        >
          🆕 New Chat
        </button>
        <ChatHistory
          onSelectChat={(id) => {
            loadSession(id);
            setIsSidebarOpen(false);
          }}
          currentSessionId={currentSessionId}
          onNewChat={startNewChat}
        />
      </div>

      <div className="chat-main">
        <div className="chat-header">
          <button
            className="menu-toggle"
            onClick={() => setIsSidebarOpen(true)}
          >
            ☰
          </button>
          <span className="app-title">Modern AI Chat</span>
          <ProjectSelector
            value={selectedProject}
            onChange={handleProjectChange}
          />
          <ModelSelector
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
          />
          {currentSessionCost > 0 && (
            <span className="session-total-cost">
              Total Usage: ${currentSessionCost?.toFixed(10)}
            </span>
          )}
        </div>
        <div className="chat-window">
          {chat.map((c, i) => (
            <div key={i} className={`message-row ${c.role}`}>
              <div className="message-content">
                <div className="avatar">{c.role === "user" ? "U" : "AI"}</div>
                <div className="text-wrapper">
                  <div className="sender-name">
                    {c.role === "user" ? "You" : "Assistant"}
                  </div>

                  <div className="message-text">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }) {
                          const match = /language-(\w+)/.exec(className || "");
                          return !inline && match ? (
                            <SyntaxHighlighter
                              style={vscDarkPlus}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {String(children).replace(/\n$/, "")}
                            </SyntaxHighlighter>
                          ) : (
                            <code className={className} {...props}>
                              {children}
                            </code>
                          );
                        },
                      }}
                    >
                      {c.text}
                    </ReactMarkdown>
                  </div>

                  {(c.images ?? (c.image ? [c.image] : [])).map((src, index) => (
                    <img
                      key={`${i}-${index}`}
                      src={src}
                      alt={`Uploaded image ${index + 1}`}
                      className="chat-img"
                    />
                  ))}

                  {c.role === "bot" && c.usage && (
                    <div className="usage-stats">
                      <span>{c.usage?.total_tokens || "0"} tokens</span>
                      <span className="separator">•</span>
                      <span>
                        $
                        {c.usage?.estimated_cost_usd
                          ? c.usage.estimated_cost_usd.toFixed(10)
                          : "0.0000000000"}
                      </span>
                      <span className="separator">•</span>
                      <span className="">
                        {c.usage?.model_used ? c.usage.model_used : ""}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <div className="input-container">
          <div className="input-box-wrapper">
            <textarea
              placeholder="Message AI..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onPaste={handlePaste}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
            <div className="input-actions">
              <label className="file-label">
                📎 Attach{" "}
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  hidden
                  ref={fileInputRef}
                  onChange={(e) => {
                    addImages(e.target.files);
                    e.target.value = ""
                }}
                />
                {images.length > 0 && (
                  <div className="image-preview-list">
                    {images.map((file, index) => (
                      <div
                        className="image-preview-item"
                        key={`${file.name}-${index}`}
                      >
                        <img src={imagePreviewUrls[index]} alt={file.name} />
                        <span className="image-preview-name">{file.name}</span>
                        <button
                          type="button"
                          aria-label={`Remove ${file.name}`}
                          onClick={() =>
                            setImages((current) =>
                              current.filter((_, i) => i !== index),
                            )
                          }
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </label>
              <button
                className="send-btn"
                onClick={sendMessage}
                disabled={!canSend}
              >
                {isSending ? "Sending..." : "Send"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
