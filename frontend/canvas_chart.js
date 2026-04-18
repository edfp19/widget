(function (global) {
    'use strict';

    function renderXgChart(panel, data) {
        panel.innerHTML = '<div class="sr-panel-heading">xG Race</div>';

        var canvas = document.createElement('canvas');
        canvas.className = 'sr-xg-canvas';
        panel.appendChild(canvas);

        function draw() {
            var rect = panel.getBoundingClientRect();
            var width = Math.max(Math.floor(rect.width) - 24, 280);
            var height = 260;
            var padding = 24;
            var maxMinute = Math.max.apply(Math, data.timeline_minute.concat([90]));
            var maxXg = Math.max.apply(Math, data.home_xg_cumulative.concat(data.away_xg_cumulative, [1]));
            var widgetRoot = panel.closest('.sr-widget-root') || panel;
            var styles = getComputedStyle(widgetRoot);
            var homeColor = styles.getPropertyValue('--sr-home-color').trim() || '#d06b2f';
            var awayColor = styles.getPropertyValue('--sr-away-color').trim() || '#1d6f8c';

            canvas.width = width;
            canvas.height = height;

            var context = canvas.getContext('2d');
            context.clearRect(0, 0, width, height);
            context.fillStyle = '#fffdf7';
            context.fillRect(0, 0, width, height);

            context.strokeStyle = '#d8d4ca';
            context.lineWidth = 1;
            context.beginPath();
            context.moveTo(padding, height - padding);
            context.lineTo(width - padding, height - padding);
            context.lineTo(width - padding, padding);
            context.stroke();

            drawStepLine(context, data.timeline_minute, data.home_xg_cumulative, function (minute) {
                return padding + ((width - (padding * 2)) * minute / maxMinute);
            }, function (value) {
                return height - padding - ((height - (padding * 2)) * value / maxXg);
            }, homeColor);

            drawStepLine(context, data.timeline_minute, data.away_xg_cumulative, function (minute) {
                return padding + ((width - (padding * 2)) * minute / maxMinute);
            }, function (value) {
                return height - padding - ((height - (padding * 2)) * value / maxXg);
            }, awayColor);

            context.fillStyle = '#2c261c';
            context.font = '12px Arial, sans-serif';
            context.fillText(data.home_team, padding, 16);
            context.fillText(data.away_team, width - padding - 90, 16);
        }

        draw();

        if (typeof ResizeObserver === 'function') {
            var observer = new ResizeObserver(draw);
            observer.observe(panel);
            canvas._destroyChart = function () {
                observer.disconnect();
            };
        }
    }

    function drawStepLine(context, minutes, values, xScale, yScale, color) {
        context.beginPath();
        context.strokeStyle = color;
        context.lineWidth = 3;

        minutes.forEach(function (minute, index) {
            var x = xScale(minute);
            var y = yScale(values[index]);

            if (index === 0) {
                context.moveTo(xScale(0), y);
                context.lineTo(x, y);
                return;
            }

            context.lineTo(x, yScale(values[index - 1]));
            context.lineTo(x, y);
        });

        context.stroke();
    }

    global.renderXgChart = renderXgChart;
}(window));
