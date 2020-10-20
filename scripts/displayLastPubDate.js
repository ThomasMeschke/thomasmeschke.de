function loadLastPublishedDateInto(elementId){
    let environment = determineCurrentEnvironment();
    console.debug(environment);
    writeLastPublishedDateForEnvIntoElement(environment, elementId);
}

function determineCurrentEnvironment(){
    let currentUrl = window.location.href;
    if(currentUrl.includes("dev.")){
        return "dev";
    }
    return "live";
}

function writeLastPublishedDateForEnvIntoElement(environment, elementId){
    let xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function(){
        if (this.readyState == 4 && this.status == 200){
            displayLastPublishedDate(elementId, this.responseText);
        }
    };
    xhttp.open("GET", "pubdate_" + environment + ".inf", true);
    xhttp.send();

}

function displayLastPublishedDate(elementId, lastPublishedDate){
    document.getElementById(elementId).innerHTML = lastPublishedDate;
}