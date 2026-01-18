// Wait for the page to fully load before running the code
document.addEventListener('DOMContentLoaded', async () => {
    const appDiv = document.getElementById('app');

    // Step 1: Fetch questions from the backend API
    const response = await fetch('/questions');
    const questions = await response.json();

    // Step 2: Dynamically create and render the form HTML
    let formHtml = '<form id="surveyForm">';
    questions.forEach(question => {
        formHtml += `
            <label for="q${question.id}">${question.text}</label>
            <input type="text" id="q${question.id}" data-qid="${question.id}" required />
        `;
    });
    formHtml += '<button type="submit">Submit Answers</button></form>';
    appDiv.innerHTML = formHtml;

    // Step 3: Add event listener for form submission
    document.getElementById('surveyForm').addEventListener('submit', async (event) => {
        // Prevent the default form submission (page reload)
        event.preventDefault();

        // Step 4: Collect answers from all input fields
        const inputs = appDiv.querySelectorAll('input[data-qid]');
        const answers = Array.from(inputs).map(input => ({
            questionId: parseInt(input.dataset.qid),
            answer: input.value.trim()
        }));

        // Step 5: Prepare payload matching backend expectation
        const payload = { answers };

        // Step 6: Send answers to backend via POST
        const submitResponse = await fetch('/answers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        // Step 7: On success, hide form and show thank-you message
        if (submitResponse.ok) {
            appDiv.innerHTML = '<p>Thank you for your answers!</p>';
        } else {
            appDiv.innerHTML = '<p>Something went wrong. Please try again.</p>';
        }
    });
});
