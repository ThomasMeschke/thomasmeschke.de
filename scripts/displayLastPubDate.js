function loadLastPublishedDateInto(elementId){
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function(){
        if (this.readyState == 4 && this.status == 200){
            displayLastPublishedDate(elementId, this.responseText);
        }
    };
    xhttp.open("GET", "pubdate.inf", true);
    xhttp.send();
}

function displayLastPublishedDate(elementId, lastPublishedDate){
    document.getElementById(elementId).innerHTML = lastPublishedDate;
}