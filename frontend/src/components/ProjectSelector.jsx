import { useEffect, useState } from "react";

const API_URL = "http://localhost:8000";

export default function ProjectSelector({ value, onChange }) {
  const [projects, setProjects] = useState([]);
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/agent/projects`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load projects.");
        return response.json();
      })
      .then((data) => {
        setProjects(data.projects ?? []);

        const saved = localStorage.getItem("selectedProject");
        const initialProject =
          saved && data.projects.includes(saved)
            ? saved
            : data.default_project || data.projects[0] || "";

        if (initialProject && initialProject !== value) {
          onChange(initialProject);
        }
      })
      .catch(() => setStatus("Could not load projects."));
    // Load project names once when this selector appears.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleIndex = async () => {
    if (!value) return;

    setStatus("Indexing project…");

    try {
      const response = await fetch(`${API_URL}/agent/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: value }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Indexing failed.");
      }

      setStatus(`Indexed ${data.indexed_chunks} text chunks.`);
    } catch (error) {
      setStatus(error.message || "Could not index project.");
    }
  };

  return (
    <div className="project-selector">
      <select
        value={value}
        onChange={(event) => {
          const project = event.target.value;
          localStorage.setItem("selectedProject", project);
          onChange(project);
        }}
        aria-label="Selected project"
      >
        <option value="" disabled>
          Select project
        </option>

        {projects.map((project) => (
          <option key={project} value={project}>
            {project}
          </option>
        ))}
      </select>

      <button type="button" onClick={handleIndex} disabled={!value}>
        Index project
      </button>

      {status && <span role="status">{status}</span>}
    </div>
  );
}