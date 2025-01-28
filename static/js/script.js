document.getElementById("videoForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const formData = new FormData(this);
    const response = await fetch("/create_video", {
        method: "POST",
        body: formData,
    });

    const { task_id } = await response.json();
    const progressDiv = document.getElementById("progress");

    // Poll for task status
    const interval = setInterval(async () => {
        const res = await fetch(`/task_status/${task_id}`);
        const data = await res.json();

        if (data.state === "SUCCESS") {
            clearInterval(interval);
            progressDiv.innerHTML = `Vidéo créée avec succès ! ID YouTube: ${data.result.video_id}`;
        } else if (data.state === "FAILURE") {
            clearInterval(interval);
            progressDiv.innerHTML = `Erreur: ${data.error}`;
        } else {
            progressDiv.innerHTML = `Progression: ${data.progress || 0}%`;
        }
    }, 1000);
});
