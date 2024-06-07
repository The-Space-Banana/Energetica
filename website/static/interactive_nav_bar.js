/* 
This code marks the current page in green in the navigation bar on the left.
*/

const activePage = window.location.pathname;
const navLinks = document.querySelectorAll("nav a").forEach((link) => {
    if (link.href.includes(`${activePage}`)) {
        if (activePage == "/profile" && window.location.href.includes("player_id")) {
            expand_menu("community");
        }else{
            link.classList.add("active");
            link.querySelector("img").classList.add("active");
        }
        if (link.href.includes("facilities")) {
            expand_menu("facilities");
        } else if (link.href.includes("overview")) {
            expand_menu("overview");
        }
    }
});

function expand_menu(id) {
    let dropdown = document.getElementById("menu-" + id);
    let dropdown_icon = document.getElementById("dropdown-" + id);
    dropdown.classList.toggle("show");
    dropdown_icon.classList.toggle("rotate");
    if(id == "community"){
        const community_badge = document.getElementById("unread_badge_community");
        if(community_badge){
            community_badge.classList.toggle("hidden");
        }
    }
}

function show_notification_list(){
    document.getElementById('notification_popup').classList.remove('hidden');
    let notification_list = document.getElementById('notification_list');
    notification_list.scrollTop = notification_list.scrollHeight;
}

function scroll_down_small_notification_list(){
    let notification_list = document.getElementById('notification_list-small');
    notification_list.scrollTop = notification_list.scrollHeight;
}

scroll_down_small_notification_list();