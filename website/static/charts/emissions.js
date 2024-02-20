const keys_emissions = [
    "steam_engine",
    "coal_burner",
    "oil_burner",
    "gas_burner",
    "combined_cycle",
    "nuclear_reactor",
    "nuclear_reactor_gen4",
    "construction",
    "coal_mine",
    "oil_field",
    "gas_drilling_site",
    "uranium_mine",
];

function draw() {
    if (graph) {
        push();
        fill_alt = 1;
        image(graph, 0, 0);
        translate(0, 10);
        push();
        stroke(255);
        strokeWeight(2);
        let X = min(graph_w, max(0, mouseX - 1.5 * margin));
        let t = floor(map(X, 0, graph_w, 0, data_len));
        X += 1.5 * margin;
        if (t == data_len) {
            t = data_len - 1;
        }
        line(X, 0, X, graph_h);
        noStroke();
        translate(X, graph_h);
        let lines = 1;
        let h_max = 0;
        let total_power = 0;
        for (const key of keys_emissions) {
            if (key in data){
                if (data[key][t] > 0) {
                    let h = (-data[key][t] / maxSum) * graph_h;
                    ellipse(0, h, 8, 8);
                    translate(0, h);
                    lines += 1;
                    h_max -= h;
                    total_power += data[key][t] * 60;
                }
            }
        }
        let tx = -180;
        let ty = 0;
        if (h_max < (lines + 1) * 16) {
            ty = h_max - (lines + 1) * 16 - 2;
        }
        if (t / data_len < 180 / graph_w) {
            tx = 20;
        }
        translate(tx, ty);
        alternate_fill();
        fill_alt = 1 - (lines % 2);
        rect(0, 0, 160, 17);
        fill(0);
        textFont(balooBold);
        text(display_duration((data_len - t - 1) * res_to_factor[res]), 80, 5);
        textFont(font);
        translate(0, 16 * lines);
        alternate_fill();
        rect(0, 0, 160, 17);
        fill(0);
        textFont(balooBold);
        text("TOTAL :", 40, 6);
        text(display_kgh_long(total_power), 120, 6);
        textFont(font);
        for (const key of keys_emissions) {
            if (key in data){
                if (data[key][t] > 0) {
                    alternate_fill();
                    translate(0, -16);
                    rect(0, 0, 160, 17);
                    push();
                    fill(cols_and_names[key][0]);
                    rect(0, 0, 16, 17);
                    pop();
                    fill(0);
                    textAlign(LEFT, CENTER);
                    text(cols_and_names[key][1], 20, 5);
                    textAlign(CENTER, CENTER);
                    text(display_kgh(data[key][t] * 60), 135, 5);
                    fill(229, 217, 182);
                }
            }
        }
        pop();
        pop();
    }
}

function regen(res) {
    load_chart_data()
        .then((raw_data) => {
            console.log(raw_data);
            background(229, 217, 182);
            Object.keys(raw_data["emissions"]).forEach((key) => {
                data[key] = reduce(raw_data["emissions"][key], res);
            });
            data_len = data["steam_engine"].length;
            push();
            translate(1.5 * margin, height - 2 * margin - 10);
            noStroke();
            const sumArray = Array.from({ length: data_len }, (_, i) =>
                Object.values(data).reduce((acc, arr) => acc + arr[i], 0)
            );
            maxSum = Math.max(...sumArray);
            if (maxSum == 0) {
                maxSum = 100;
            }
            push();
            for (let t = 0; t < data_len; t++) {
                push();
                for (const key of keys_emissions) {
                    if (key in data){
                        if (data[key][t] > 0) {
                            fill(cols_and_names[key][0]);
                            let h = (data[key][t] / maxSum) * graph_h;
                            rect(0, 0, graph_w / data_len + 1, -h - 1);
                            translate(0, -h);
                        }
                    }
                }
                pop();
                translate(graph_w / data_len, 0);
            }
            pop();
            stroke(0);
            line(0, 0, graph_w, 0);
            line(0, 0, 0, -graph_h);

            push();
            let units = time_unit(res);
            fill(0);
            for (let i = 0; i < units.length; i++) {
                stroke(0, 0, 0, 30);
                let x = (i * graph_w) / (units.length - 1);
                line(x, -graph_h, x, 0);
                stroke(0);
                line(x, 0, x, 5);
                noStroke();
                text(units[i], x, 0.3 * margin);
            }
            pop();

            push();
            let y_ticks = y_units(maxSum * 60);
            let interval = y_ticks[1];
            fill(0);
            let y = map(interval, 0, maxSum * 60, 0, graph_h);
            for (let i = 0; i < y_ticks.length; i++) {
                stroke(0, 0, 0, 30);
                line(graph_w, -y * i, 0, -y * i);
                stroke(0);
                line(0, -y * i, -5, -y * i);
                noStroke();
                text(display_kgh(y_ticks[i]), -0.75 * margin, -y * i - 4);
            }
            pop();
            pop();

            for (let i = 0; i < buttons.length; i++) {
                push();
                translate(
                    1.5 * margin + (i * graph_w) / buttons.length,
                    height - margin - 10
                );
                buttons[i].display_button();
                pop();
            }

            graph = get();
        })
        .catch((error) => {
            console.error("Error:", error);
        });
}

function calc_size() {
    graph_h = height - 2 * margin - 20;
    graph_w = width - 3 * margin;
}
