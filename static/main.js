window.onload = function () {
    console.log("!!!!! WERE IN")
    document.querySelectorAll("#location_form form").forEach(function (form) {
        console.log("BOOO")
        for (let opt of form.children) {
            opt.oninput = function () {
                console.log("YYYYS")
                form.submit()
            }
        }
    })
    document.querySelectorAll("select#history_location").forEach(function (select) {
        console.log("GIIIIIRRRRRRRR")
        select.oninput = function () {
            console.log("LSSSSSSSZ")
            document.querySelector("#history_form").submit()
        }
    })
    document.querySelector("#reset").onclick = function () {
        function setVisible(selector, visible) {
            document.querySelector(selector).style.display = visible ? 'block' : 'none';
        }
        setVisible('#loadertext', true);
        setVisible('#loader', true);
        setVisible('.page', false);
        fetch("/resetdb", {method:'POST'})
            .then(response => response.json())
                .then(data => {
                    console.log(data)
                    setVisible('#loader', false);
                    setVisible('.page', true);
                    setVisible('#success', true);
                    setVisible('#loadertext', false);
                });
    }
}


