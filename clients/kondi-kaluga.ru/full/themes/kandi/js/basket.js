    $(document).ready(function(){    
        $(".order_btn a").click(function()
        {
            var price;
            
            if($(this).parent().parent().siblings("p").children(".price").html())
            {
                price = parseInt($(this).parent().parent().siblings("p").children(".price").html());
            }
            else  price = 0;

            console.log(price);
            
            var image =  $(this).parent().parent().parent().siblings(".product_img").children("a").children("img");
            
            var basketPos = $(".product_count").offset();
            var imagePos = $(image).offset();
            var imgClone = $(image).clone();
            $("body").append(imgClone);
            $(imgClone).css({"position":"absolute", "left":imagePos.left, "top": imagePos.top, "z-index":1000});
            $(imgClone).animate({"opacity" : .5, "top": basketPos.top, "left": basketPos.left}, 800, function(){$(this).remove(); $("span.product_count").animate({"opacity":0}, 200, function(){$("span.product_count").animate({"opacity":1}, 900)})});
            
            /*Общее количество*/
            var isset_summ = parseInt($("span.product_count").html());            
            var amount = isset_summ+1;

            /*Общая цена*/
            
            var isset_price = parseInt($(".amount").html());
            var all_price = isset_price + price;

            $("span.product_count").html(amount);
            $(".amount").html(all_price);
            
            var product_id = parseInt($(this).parent().parent().parent().attr("id").substr(8))
            
            var product_ids = '';
            var price = '';
            var all_amount = '';
            if($.cookie("products"))
            {
                product_ids = $.cookie("products");
            }
            
            if($.cookie("price"))
            {
                price = $.cookie("price");
            }
            if($.cookie("amount"))
            {
                all_amount = $.cookie("amount");
            }            
            
            if(price != '')
            {
                price = all_price // + parseInt(price);
            }
            else{
                price = all_price;
            }
            
            if(all_amount != '')
            {
                all_amount = amount //+ parseInt(all_amount);
            }
            else
            {
                all_amount = amount;
            }            

            
            if(product_ids != '') product_ids = product_ids+","+ product_id;
            else product_ids = product_id;
            
            
            $.cookie("products", product_ids, { expires: 1, path: '/'});
            $.cookie("price", price, { expires: 1, path: '/' });
            $.cookie("amount", all_amount, { expires: 1, path: '/' });
            
        });
        
    });