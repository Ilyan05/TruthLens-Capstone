/* ==========================================================================
   TruthLens - Shared frontend JS
   Handles: form submission (text/image/audio) + file preview
   ========================================================================== */

/**
 * Wires a form to POST its data (JSON for text, FormData for files)
 * to the endpoint in data-endpoint, and renders the response in resultBoxId.
 */
function initVerifyForm(formId, resultBoxId) {
  const form = document.getElementById(formId);
  const resultBox = document.getElementById(resultBoxId);
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const endpoint = form.dataset.endpoint;
    const submitBtn = form.querySelector("button[type='submit']");

    submitBtn.disabled = true;
    submitBtn.textContent = "Analyzing...";
    showResult(resultBox, `<p class="status-line">⏳ Submitting to TruthLens pipeline...</p>`);

    try {
      const formData = new FormData(form); // works for text (textarea) and file inputs alike
      const res = await fetch(endpoint, { method: "POST", body: formData });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Server responded ${res.status}: ${errText}`);
      }

      const data = await res.json();
      renderSubmissionResult(resultBox, data);
    } catch (err) {
      resultBox.classList.add("error");
      showResult(resultBox, `<p class="status-line">❌ ${err.message}</p>`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Analyze " + (formId.includes("text") ? "Claim" : formId.includes("image") ? "Image" : "Audio");
    }
  });
}

function renderSubmissionResult(resultBox, data) {
  resultBox.classList.remove("error");
  showResult(resultBox, `
    <h4>✅ Submission Received</h4>
    <p class="status-line"><strong>Submission ID:</strong> ${data.submission_id}</p>
    <p class="status-line"><strong>Content Type:</strong> ${data.content_type}</p>
    <p class="status-line"><strong>Status:</strong> ${data.status}</p>
    <p class="status-line">Verdict pipeline result will appear here once the backend agents are connected.</p>
  `);
}

function showResult(resultBox, html) {
  resultBox.classList.remove("hidden");
  resultBox.innerHTML = html;
}

/**
 * Shows a live preview for a file input (image <img> or audio <audio>).
 */
function initFilePreview(inputId, previewId) {
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  if (!input || !preview) return;

  input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    if (preview.tagName === "IMG") {
      preview.src = url;
    } else if (preview.tagName === "AUDIO") {
      preview.src = url;
    }
    preview.classList.remove("hidden");
  });
}