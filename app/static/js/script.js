const socket = io();

const chatDiv = document.getElementById('chat');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');

function addMessage(sender, message) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    messageDiv.textContent = `${sender}: ${message}`;
    chatDiv.appendChild(messageDiv);
    chatDiv.scrollTop = chatDiv.scrollHeight;
}

socket.on('new_message', (data) => {
    addMessage(data.sender, data.message);
});

startBtn.addEventListener('click', async () => {
    startBtn.disabled = true;
    stopBtn.disabled = false;

    const response = await fetch('/start', {
        method: 'POST',
    });

    const result = await response.json();
    if (result.status === 'success') {
        const audioUrl = result.signed_url; // Get the signed URL for audio
        audioPlayer.src = audioUrl; // Set the audio source
        audioPlayer.play(); // Play the audio
        addMessage('system', 'Conversation started.');

    } else {
        addMessage('system', 'Failed to start conversation: ' + result.message);
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
});

stopBtn.addEventListener('click', async () => {
    stopBtn.disabled = true;
    startBtn.disabled = false;

    const response = await fetch('/stop', {
        method: 'POST',
    });

    const result = await response.json();
    if (result.status === 'success') {
        addMessage('system', 'Conversation stopped.');
    } else {
        addMessage('system', 'Failed to stop conversation.');
        stopBtn.disabled = false;
        startBtn.disabled = true;
    }
});

window.onload = async () => {
    const response = await fetch('/transcript');
    const result = await response.json();
    result.transcript.forEach((msg) => {
        addMessage(msg.sender, msg.message);
    });
};
