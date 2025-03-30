// Get CSRF token from cookies
function getCSRFToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        document.cookie.split(';').forEach(cookie => {
            let trimmedCookie = cookie.trim();
            if (trimmedCookie.startsWith("csrftoken=")) {
                cookieValue = trimmedCookie.substring(10);
            }
        });
    }
    return cookieValue;
}

// Trigger logout synchronously on tab closure
function triggerLogout() {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/logout/', false);  // Synchronous request
    xhr.setRequestHeader('X-CSRFToken', getCSRFToken());
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send();
    
    if (xhr.status === 200) {
        console.log("Logout successful on tab close from room.html");
        sessionStorage.clear();
        localStorage.clear();
        window.location.href = "/login/";  // Redirect after logout
    } else {
        console.error("Logout failed during tab close:", xhr.status);
    }
}

// Automatic logout on tab close
window.addEventListener("beforeunload", function(event) {
    triggerLogout();
});
document.addEventListener("DOMContentLoaded", function () {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Create Room
    const createRoomModal = document.getElementById("createRoomModal");
    createRoomModal.addEventListener("show.bs.modal", function () {
        fetch("/create-room/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/json",
            },
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                document.getElementById("roomCodeDisplay").textContent = data.room_code;
                document.getElementById("roomCodeContainer").style.display = "block";
                document.getElementById("goToDashboard").style.display = "block";

                sessionStorage.setItem("roomCode", data.room_code);
            })
            .catch((error) => {
                console.error("Error:", error);
                alert("Failed to create room");
            });
    });

    // Copy Room Code Function
    window.copyRoomCode = function () {
        const roomCode = document.getElementById("roomCodeDisplay").textContent;
        navigator.clipboard.writeText(roomCode)
            .then(() => alert("Room code copied!"))
            .catch((err) => console.error("Failed to copy:", err));
    };
    // Go to Dashboard Button
    document.getElementById("goToDashboard").addEventListener("click", function () {
        window.location.href = "/dashboard/";
    });
    // Join Room
    const joinRoomForm = document.getElementById("joinRoomForm");
    joinRoomForm.addEventListener("submit", function (e) {
        e.preventDefault();

        const roomCode = document.getElementById("roomCode").value;
        if (!roomCode) {
            alert("Please enter a room code.");
            return;
        }
        const formData = new URLSearchParams();  // Ensuring proper encoding
        formData.append("room_code", roomCode);

        fetch("/join-room/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: formData.toString(),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                sessionStorage.setItem("roomCode", data.room_code);
                window.location.href = "/dashboard/";
            })
            .catch((error) => {
                console.error("Error:", error);
                alert("Failed to join room");
            });
    });
});