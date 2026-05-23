const revenueChart = document
.getElementById('revenueChart');

new Chart(revenueChart, {

    type: 'line',

    data: {

        labels: [
            'Jan',
            'Feb',
            'Mar',
            'Apr',
            'May',
            'Jun'
        ],

        datasets: [{
            label: 'Revenue',

            data: [
                12000,
                19000,
                30000,
                25000,
                40000,
                50000
            ],

            borderWidth: 2
        }]
    }
});

const invoiceChart = document
.getElementById('invoiceChart');

new Chart(invoiceChart, {

    type: 'doughnut',

    data: {

        labels: [
            'Paid',
            'Pending',
            'Overdue'
        ],

        datasets: [{
            data: [12, 5, 2],
            borderWidth: 1
        }]
    }
});