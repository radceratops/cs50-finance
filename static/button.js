$(document).ready(function(){
    $("button").click(function(){
        // Get number of shares to be bought or sold from user
        var stock = $(this).attr("value")
        var action = $(this).data('action');
    	var quantity = prompt(`How many shares of ${stock} would you like to ${action}?`, 1);

    	if (quantity > 0) {
    	    if (action == 'sell') {
    	        alert(`${quantity} shares of ${stock} sold`);
    	        $.ajax({
            	    url: "/sell",
            	    type: 'POST',
            	    data: {
            	        'stock': stock,
            	        'shares': quantity
            	    }
            	});
    	    }
    	    else if (action == 'buy') {
    		    alert(`${quantity} shares of ${stock} bought`);
    		    $.ajax({
            	    url: "/buy",
            	    type: 'POST',
            	    data: {
            	        'stock': stock,
            	        'shares': quantity
            	    }
            	});
    	    }
    	}
    	else {
    		alert(`You did not specify your number of shares of ${stock} to ${action}.`);
    	}

    	// refresh page to show updates
    	location.reload()
    });
});
