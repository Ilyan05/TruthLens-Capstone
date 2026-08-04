async function verifyClaim() {

    const text = document.getElementById("inputText").value;

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/predict",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    text: text
                })
            }
        );

        const data = await response.json();

        document.getElementById("result").innerText =
            data.prediction;

    } catch (error) {

        document.getElementById("result").innerText =
            "Backend connection failed";

        console.error(error);
    }
}