/* 
This code contains the main functions that communicate with the server (client side)
*/

function send_form(endpoint, body) {
    return fetch(endpoint, {
        method: "POST",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
}

socket.on("connect", function () {
    console.log("Connected to server");
    socket.emit("give_identity");
});

// information sent to the server when a new facility is created
function start_construction(facility, family) {
    send_form("/request_start_project", {
        facility: facility,
        family: family,
    })
        .then((response) => {
            response.json().then((raw_data) => {
                let response = raw_data["response"];
                if (response == "success") {
                    let money = raw_data["money"];
                    var obj = document.getElementById("money");
                    obj.innerHTML = formatted_money(money);
                    addToast("Construction started");
                    sessionStorage.setItem("constructions", JSON.stringify(raw_data["constructions"]));
                    refresh_progressBar();
                } else if (response == "noSuitableLocationAvailable") {
                    addError("No suitable locations");
                } else if (response == "notEnoughMoneyError") {
                    addError("Not enough money");
                } else if (response == "locked") {
                    addError("Facility is locked! Nice try 😉");
                }
            });
        })
        .catch((error) => {
            console.error(`caught error ${error}`);
        });
}

// updates specific fields of the page without reloading
socket.on("update_data", function (changes) {
    for (i = 0; i < changes.length; i++) {
        object_id = changes[i][0];
        value = changes[i][1];
        var obj = document.getElementById(object_id);
        if (obj != null) {
            obj.innerHTML = value;
        }
    }
});

socket.on("display_new_message", function (msg) {
    var obj = document.getElementById("messages_field");
    if (obj != null) {
        obj.innerHTML += msg;
    }
});

// reloads the page
socket.on("refresh", function () {
    window.location = window.location;
});
