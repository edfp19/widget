(function (global) {
    'use strict';

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatDate(value) {
        try {
            return new Intl.DateTimeFormat('en-GB', {
                day: '2-digit',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            }).format(new Date(value));
        } catch (error) {
            return value;
        }
    }

    function getFormBadgeClass(result) {
        if (result === 'W') {
            return 'is-win';
        }

        if (result === 'D') {
            return 'is-draw';
        }

        return 'is-loss';
    }

    function renderLeagueTable(panel, rows) {
        panel.innerHTML = [
            '<div class="sr-panel-heading">Premier League Table</div>',
            '<div class="sr-table-wrap">',
            '<table class="sr-data-table">',
            '<thead><tr><th>Pos</th><th>Team</th><th>P</th><th>GD</th><th>Pts</th><th>Form</th></tr></thead>',
            '<tbody>',
            rows.map(function (row) {
                return [
                    '<tr>',
                    '<td>' + row.position + '</td>',
                    '<td>' + escapeHtml(row.team_name) + '</td>',
                    '<td>' + row.played + '</td>',
                    '<td>' + row.gd + '</td>',
                    '<td><strong>' + row.points + '</strong></td>',
                    '<td><div class="sr-form-row">',
                    row.form.map(function (result) {
                        return '<span class="sr-form-badge ' + getFormBadgeClass(result) + '">' + result + '</span>';
                    }).join(''),
                    '</div></td>',
                    '</tr>'
                ].join('');
            }).join(''),
            '</tbody></table></div>'
        ].join('');
    }

    function renderFixtures(panel, fixtures) {
        panel.innerHTML = [
            '<div class="sr-panel-heading">Fixtures and Results</div>',
            '<div class="sr-fixtures-list">',
            fixtures.map(function (fixture) {
                var score = fixture.home_score == null || fixture.away_score == null
                    ? 'vs'
                    : fixture.home_score + ' - ' + fixture.away_score;

                return [
                    '<div class="sr-fixture-row">',
                    '<div class="sr-fixture-meta">' + escapeHtml(formatDate(fixture.date)) + '</div>',
                    '<div class="sr-fixture-main">',
                    '<span>' + escapeHtml(fixture.home_team) + '</span>',
                    '<strong>' + escapeHtml(score) + '</strong>',
                    '<span>' + escapeHtml(fixture.away_team) + '</span>',
                    '</div>',
                    '<div class="sr-fixture-status">' + escapeHtml(fixture.status.toUpperCase()) + '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function renderTeamStats(panel, data) {
        var statKeys = [
            ['goals_for_avg', 'Goals For'],
            ['goals_against_avg', 'Goals Against'],
            ['xg_for_avg', 'xG For'],
            ['xg_against_avg', 'xG Against'],
            ['possession_pct', 'Possession'],
            ['shots_per_game', 'Shots'],
            ['shots_on_target_per_game', 'Shots on Target']
        ];

        panel.innerHTML = [
            '<div class="sr-panel-heading">Team Comparison</div>',
            '<div class="sr-stats-list">',
            statKeys.map(function (entry) {
                var key = entry[0];
                var label = entry[1];
                var homeValue = Number(data.home[key]);
                var awayValue = Number(data.away[key]);
                var maxValue = Math.max(homeValue, awayValue, 1);
                var homeWidth = (homeValue / maxValue) * 100;
                var awayWidth = (awayValue / maxValue) * 100;

                return [
                    '<div class="sr-stat-row">',
                    '<div class="sr-stat-label">' + escapeHtml(label) + '</div>',
                    '<div class="sr-stat-values">',
                    '<div class="sr-stat-team">',
                    '<span>' + escapeHtml(String(homeValue)) + '</span>',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-home" style="width: ' + homeWidth + '%;"></div></div>',
                    '</div>',
                    '<div class="sr-stat-team is-away">',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-away" style="width: ' + awayWidth + '%;"></div></div>',
                    '<span>' + escapeHtml(String(awayValue)) + '</span>',
                    '</div>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function renderH2H(panel, options) {
        panel.innerHTML = [
            '<div class="sr-panel-heading">Head to Head</div>',
            '<div class="sr-h2h-layout">',
            '<div class="sr-h2h-results"></div>',
            '<div class="sr-h2h-player-card">',
            '<div class="sr-h2h-selectors"></div>',
            '<div class="sr-h2h-player-comparison"><div class="sr-tab-placeholder">Choose two players to compare.</div></div>',
            '</div>',
            '</div>'
        ].join('');

        renderH2HResults(panel.querySelector('.sr-h2h-results'), options.results);
        setupH2HPlayerSelector(
            panel.querySelector('.sr-h2h-selectors'),
            panel.querySelector('.sr-h2h-player-comparison'),
            options
        );
    }

    function renderH2HResults(target, results) {
        target.innerHTML = [
            '<div class="sr-subheading">Recent Meetings</div>',
            '<div class="sr-h2h-results-list">',
            results.map(function (match) {
                var outcome = match.home_score > match.away_score ? 'W' : (match.home_score === match.away_score ? 'D' : 'L');

                return [
                    '<div class="sr-h2h-result-row">',
                    '<span class="sr-form-badge ' + getFormBadgeClass(outcome) + '">' + outcome + '</span>',
                    '<div>',
                    '<div class="sr-h2h-scoreline">' + escapeHtml(match.home_team) + ' ' + match.home_score + ' - ' + match.away_score + ' ' + escapeHtml(match.away_team) + '</div>',
                    '<div class="sr-h2h-meta">' + escapeHtml(match.match_date) + ' | xG ' + match.home_xg + ' - ' + match.away_xg + '</div>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function setupH2HPlayerSelector(selectorRoot, comparisonRoot, options) {
        var homeSelect = document.createElement('select');
        var awaySelect = document.createElement('select');

        homeSelect.innerHTML = ['<option value="">Home player</option>'].concat(
            options.selectorData.home_players.map(function (player) {
                return '<option value="' + escapeHtml(player.player_id) + '">' + escapeHtml(player.name) + '</option>';
            })
        ).join('');

        awaySelect.innerHTML = ['<option value="">Away player</option>'].concat(
            options.selectorData.away_players.map(function (player) {
                return '<option value="' + escapeHtml(player.player_id) + '">' + escapeHtml(player.name) + '</option>';
            })
        ).join('');

        selectorRoot.innerHTML = '<div class="sr-subheading">Player Comparison</div>';
        selectorRoot.appendChild(homeSelect);
        selectorRoot.appendChild(awaySelect);

        async function updateComparison() {
            if (!homeSelect.value || !awaySelect.value) {
                comparisonRoot.innerHTML = '<div class="sr-tab-placeholder">Choose two players to compare.</div>';
                return;
            }

            comparisonRoot.innerHTML = '<div class="sr-tab-placeholder">Loading comparison...</div>';

            try {
                var url = options.apiBase + '/match/' + options.matchId + '/h2h/players?home_player_id=' +
                    encodeURIComponent(homeSelect.value) + '&away_player_id=' + encodeURIComponent(awaySelect.value);
                var response = await global.fetch(url);
                var payload = await response.json();
                renderPlayerComparison(comparisonRoot, payload.data);
            } catch (error) {
                comparisonRoot.innerHTML = '<div class="sr-tab-placeholder">Unable to load player comparison.</div>';
            }
        }

        homeSelect.addEventListener('change', updateComparison);
        awaySelect.addEventListener('change', updateComparison);
    }

    function renderPlayerComparison(target, data) {
        var stats = [
            ['goals', 'Goals'],
            ['assists', 'Assists'],
            ['xg', 'xG'],
            ['shots_per_game', 'Shots/Game'],
            ['pass_accuracy_pct', 'Pass Accuracy']
        ];

        target.innerHTML = [
            '<div class="sr-compare-heading">',
            '<strong>' + escapeHtml(data.home_player.name) + '</strong>',
            '<span>vs</span>',
            '<strong>' + escapeHtml(data.away_player.name) + '</strong>',
            '</div>',
            '<div class="sr-compare-list">',
            stats.map(function (entry) {
                var key = entry[0];
                var label = entry[1];
                var homeValue = Number(data.home_player[key]);
                var awayValue = Number(data.away_player[key]);
                var maxValue = Math.max(homeValue, awayValue, 1);

                return [
                    '<div class="sr-compare-row">',
                    '<div class="sr-stat-label">' + escapeHtml(label) + '</div>',
                    '<div class="sr-compare-bars">',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-home" style="width: ' + ((homeValue / maxValue) * 100) + '%;"></div></div>',
                    '<span>' + homeValue + ' / ' + awayValue + '</span>',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-away" style="width: ' + ((awayValue / maxValue) * 100) + '%;"></div></div>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function renderMatchFacts(panel, facts) {
        panel.innerHTML = [
            '<div class="sr-panel-heading">Match Facts and Commentary</div>',
            '<ul class="sr-facts-list">',
            facts.map(function (fact) {
                return '<li class="sr-fact-item" data-category="' + escapeHtml(fact.category) + '">' +
                    '<span class="sr-fact-category">' + escapeHtml(fact.category) + '</span>' +
                    '<span>' + escapeHtml(fact.text) + '</span>' +
                    '</li>';
            }).join(''),
            '</ul>'
        ].join('');
    }

    function renderSquads(panel, data, context) {
        panel.__srSquadsData = data;

        if (context && context.pageType === 'match' && context.phase === 'LIVE') {
            renderPitchView(panel);
            return;
        }

        panel.innerHTML = [
            '<div class="sr-panel-heading">Squads and Line-ups</div>',
            '<div class="sr-squads-grid">',
            renderSquadColumn(data.home),
            renderSquadColumn(data.away),
            '</div>'
        ].join('');
    }

    function renderSquadColumn(team) {
        return [
            '<section class="sr-squad-card">',
            '<div class="sr-subheading">' + escapeHtml(team.team_name) + ' (' + escapeHtml(team.formation) + ')</div>',
            '<div class="sr-squad-group"><strong>Starting XI</strong></div>',
            '<ul class="sr-player-list">',
            team.starting_xi.map(function (player) {
                return '<li>' + player.number + ' ' + escapeHtml(player.name) + ' <span>' + escapeHtml(player.position) + '</span></li>';
            }).join(''),
            '</ul>',
            '<div class="sr-squad-group"><strong>Bench</strong></div>',
            '<ul class="sr-player-list">',
            team.bench.map(function (player) {
                return '<li>' + player.number + ' ' + escapeHtml(player.name) + ' <span>' + escapeHtml(player.position) + '</span></li>';
            }).join(''),
            '</ul>',
            '</section>'
        ].join('');
    }

    function renderPitchView(panel) {
        var data = panel.__srSquadsData;

        if (!data) {
            panel.innerHTML = '<div class="sr-tab-placeholder">Pitch view is not ready yet.</div>';
            return;
        }

        panel.innerHTML = [
            '<div class="sr-panel-heading">Live Formation View</div>',
            '<div class="sr-pitch-grid">',
            renderPitchTeam(data.home),
            renderPitchTeam(data.away),
            '</div>'
        ].join('');
    }

    function renderPitchTeam(team) {
        return [
            '<section class="sr-pitch-card">',
            '<div class="sr-subheading">' + escapeHtml(team.team_name) + '</div>',
            '<div class="sr-pitch-surface">',
            team.starting_xi.map(function (player) {
                return '<div class="sr-player-node" style="left: ' + player.position_x + '%; top: ' + player.position_y + '%;">' +
                    '<span>' + player.number + '</span><small>' + escapeHtml(player.name) + '</small>' +
                    '</div>';
            }).join(''),
            '</div>',
            '</section>'
        ].join('');
    }

    global.renderPitchView = renderPitchView;
    global.SRRenderers = {
        renderLeagueTable: renderLeagueTable,
        renderFixtures: renderFixtures,
        renderTeamStats: renderTeamStats,
        renderH2H: renderH2H,
        renderMatchFacts: renderMatchFacts,
        renderSquads: renderSquads,
        renderPitchView: renderPitchView
    };
}(window));
