var colors = ['#104060','#125b94','#1f7fc1','#67add8']

$.getJSON('scripts/testdata.json', function(data) {
    var rfcchart = c3.generate({
        bindto: '#rfcchart',
        data: {
            rows: data.rows,
            type: 'bar',
            groups: [data.groups],
            order:null,
            labels: true,
            },
        color: {
            pattern: colors
            },
        axis: {
            rotated: true,
            x: {
                type: 'category',
                categories: data.categories
                },
            y: {
                show: false
                }
            },
        legend: {
            position: 'bottom',
            item: {
                onmouseover: function (d) {
                        var d2 = d.replace(/ /g, '-')
                        var whatlabel = ".c3-texts-" + d2 + ' text';
                        $(whatlabel).css("display", "inline")
                    },
                onmouseout: function (d) {
                        var d2 = d.replace(/ /g, '-')
                        var whatlabel = ".c3-texts-" + d2 + ' text';
                        $(whatlabel).css("display", "none")
                    }
                }
            }
        })
    }
);