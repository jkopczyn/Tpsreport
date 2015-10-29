$.getJSON('scripts/testdata.json', function(data) {
    var chart = c3.generate({
    bindto: '#rfcchart',
    data: {
        rows: data.rows,
        type: 'bar',
        groups: [data.groups],
        order:null
    },
    axis: {
        rotated: true,
        x: {
            type: 'category',
            categories: data.categories
        }
    },
});
})
