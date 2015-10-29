var colors = ['#104060','#125b94','#1f7fc1','#67add8']

$.getJSON('scripts/testdata.json', function(data) {
    var rfcchart = c3.generate({
    bindto: '#rfcchart',
    data: {
        rows: data.rows,
        type: 'bar',
        groups: [data.groups],
        order:null
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
        }
    });
})

