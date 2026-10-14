
const MODELS = [
  { id: "gemma3", name: "Gemma 3 (4B)", description: "General + vision" },
  { id: "qwen2.5:3b", name: "Qwen 2.5 3B", description: "Text only" },
  { id: "qwen2.5vl:3b", name: "Qwen 2.5 VL 3B", description: "Vision" },
  { id: "qwen3-vl:2b", name: "Qwen3 VL 2B", description: "Vision, small" },
];

/**
 * A React component that displays a dropdown menu for selecting a model to use for generating responses.
 * 
 * @param {string} selectedModel - The currently selected model.
 * @param {function} onModelChange - A function that is called when the user selects a different model.
 * @returns {React.ReactElement} A React component displaying a dropdown menu with the available models.
 */
export default function ModelSelector({ selectedModel, onModelChange }) {
  return (
    <div className="model-selector">
      <select 
        value={selectedModel} 
        onChange={(e) => onModelChange(e.target.value)}
        className="model-select-dropdown"
      >
        {MODELS.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} — {m.description}
          </option>
        ))}
      </select>
    </div>
  );
}