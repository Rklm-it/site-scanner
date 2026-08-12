var ReviewImagesSection = ( function($) {

	ReviewImagesSection = function(options) {
		var that = this;

		// DOM
		that.$wrapper = options["$wrapper"];
		that.$file_field = that.$wrapper.find(".js-file-field");
		that.$files_wrapper = that.$wrapper.find(".js-attached-files-section");
		that.$errors_wrapper = that.$wrapper.find(".js-errors-section");

		// CONST
		that.max_post_size = options["max_post_size"];
		that.max_file_size = options["max_file_size"];
		that.max_files = options["max_files"];
		that.templates = options["templates"];
		that.patterns = options["patterns"];
		that.locales = options["locales"];

		// DYNAMIC VARS
		that.post_size = 0;
		that.id_counter = 0;
		that.files_data = {};
		that.images_count = 0;

		// INIT
		that.init();
	};

	ReviewImagesSection.prototype.init = function() {
		var that = this,
			$document = $(document);

		that.$wrapper.data("controller", that);

		that.$file_field.on("change", function() {
			addFiles(this.files);
			that.$file_field.val("");
		});

		that.$wrapper.on("click", ".js-show-textarea", function(event) {
			event.preventDefault();
			$(this).closest(".s-description-wrapper").addClass("is-extended");
		});

		that.$wrapper.on("click", ".js-delete-file", function(event) {
			event.preventDefault();
			var $file = $(this).closest(".s-file-wrapper"),
				file_id = "" + $file.data("file-id");

			if (file_id && that.files_data[file_id]) {
				var file_data = that.files_data[file_id];
				that.post_size -= file_data.file.size;
				delete that.files_data[file_id];
				that.images_count -= 1;
			}

			$file.remove();

			that.renderErrors();
		});

		that.$wrapper.on("keyup change", ".js-textarea", function(event) {
			var $textarea = $(this),
				$file = $textarea.closest(".s-file-wrapper"),
				file_id = "" + $file.data("file-id");

			if (file_id && that.files_data[file_id]) {
				var file = that.files_data[file_id];
				file.desc = $textarea.val();
			}
		});

		var timeout = null,
			is_entered = false;

		$document.on("dragover", dragWatcher);
		function dragWatcher(event) {
			var is_exist = $.contains(document, that.$wrapper[0]);
			if (is_exist) {
				onDrag(event);
			} else {
				$document.off("dragover", dragWatcher);
			}
		}

		$document.on("drop", dropWatcher);
		function dropWatcher(event) {
			var is_exist = $.contains(document, that.$wrapper[0]);
			if (is_exist) {
				onDrop(event)
			} else {
				$document.off("drop", dropWatcher);
			}
		}

		$document.on("reset clear", resetWatcher);
		function resetWatcher(event) {
			var is_exist = $.contains(document, that.$wrapper[0]);
			if (is_exist) {
				that.reset();
			} else {
				$document.off("reset clear", resetWatcher);
			}
		}

		function onDrop(event) {
			event.preventDefault();

			var files = event.originalEvent.dataTransfer.files;

			addFiles(files);
			dropToggle(false);
		}

		function onDrag(event) {
			event.preventDefault();

			if (!timeout)  {
				if (!is_entered) {
					is_entered = true;
					dropToggle(true);
				}
			} else {
				clearTimeout(timeout);
			}

			timeout = setTimeout(function () {
				timeout = null;
				is_entered = false;
				dropToggle(false);
			}, 100);
		}

		function dropToggle(show) {
			var active_class = "is-highlighted";

			if (show) {
				that.$wrapper.addClass(active_class);
			} else {
				that.$wrapper.removeClass(active_class);
			}
		}

		function addFiles(files) {
			var errors_types = [],
				errors = [];

			$.each(files, function(i, file) {
				var response = that.addFile(file);
				if (response.error) {
					var error = response.error;

					if (errors_types.indexOf(error.type) < 0) {
						errors_types.push(error.type);
						errors.push(error);
					}
				}
			});

			that.renderErrors(errors);
		}
	};

	ReviewImagesSection.prototype.addFile = function(file) {
		var that = this,
			file_size = file.size;

		var image_type = /^image\/(png|jpe?g|gif)$/,
			is_image = (file.type.match(image_type));

		if (!is_image) {
			return {
				error: {
					text: that.locales["file_type"],
					type: "file_type"
				}
			};

		} else if (that.images_count >= that.max_files) {
			return {
				error: {
					text: that.locales["files_limit"],
					type: "files_limit"
				}
			};

		} else if (file_size >= that.max_file_size) {
			return {
				error: {
					text: that.locales["file_size"],
					type: "file_size"
				}
			};

		} else if (that.post_size + file_size >= that.max_file_size) {
			return {
				error: {
					text: that.locales["post_size"],
					type: "post_size"
				}
			};

		} else {
			that.post_size += file_size;

			var file_id = that.id_counter,
				file_data = {
					id: file_id,
					file: file,
					desc: ""
				};

			that.files_data[file_id] = file_data;

			that.id_counter++;
			that.images_count += 1;

			render();

			return file_data;
		}

		function render() {
			var $template = $(that.templates["file"]),
				$image = $template.find(".js-image-wrapper");

			$template.attr("data-file-id", file_id);

			getImageUri().then( function(image_uri) {
				$image.css("background-image", "url(" + image_uri + ")");
			});

			that.$files_wrapper.append($template);

			function getImageUri() {
				var deferred = $.Deferred(),
					reader = new FileReader();

				reader.onload = function(event) {
					deferred.resolve(event.target.result);
				};

				reader.readAsDataURL(file);

				return deferred.promise();
			}
		}
	};

	ReviewImagesSection.prototype.reset = function() {
		var that = this;

		that.post_size = 0;
		that.id_counter = 0;
		that.files_data = {};

		that.$files_wrapper.html("");
		that.$errors_wrapper.html("");
	};

	ReviewImagesSection.prototype.getSerializedArray = function() {
		var that = this,
			result = [];

		var index = 0;

		$.each(that.files_data, function(file_id, file_data) {
			var file_name = that.patterns["file"].replace("%index%", index),
				desc_name = that.patterns["desc"].replace("%index%", index);

			result.push({
				name: file_name,
				value: file_data.file
			});

			result.push({
				name: desc_name,
				value: file_data.desc
			});

			index++;
		});

		return result;
	};

	ReviewImagesSection.prototype.renderErrors = function(errors) {
		var that = this,
			result = [];

		that.$errors_wrapper.html("");

		if (errors && errors.length) {
			$.each(errors, function(i, error) {
				if (error.text) {
					var $error = $(that.templates["error"].replace("%text%", error.text));
					$error.appendTo(that.$errors_wrapper);
					result.push($error);
				}
			});
		}

		return result;
	};

	return ReviewImagesSection;

})(jQuery);

( function($) {

    var $form_wrapper = $("#s-reviews-form"),
        $form = $form_wrapper.find("form"),
        $captcha = $(".wa-captcha"),
        $provider = $("#user-auth-provider"),
        $error_wrapper = $form.find(".errormsg").closest(".u-cen-txt"),
        current_provider = $provider.find(".selected").attr('data-provider');

    var reviews_initialize = function() {
        bindEvents();
    };

    var bindEvents = function() {
		if( 'ontouchstart' in window ){ var click = 'touchstart'; }
		else { var click = 'click'; }

        $('.reviews__btn-showform').on(click, function(){
			unsetReplyID();
            showForm();
            return false;
        });

        $(document).on("click",".rev-form__close-btn_js", function(){
            unsetReplyID();
			closeForm();
            return false;
        });

        $(document).on("click", ".rate-it__star_js", function() {
            setRating( $(this) );
            return false;
        });

        $(document).on("click", "#user-auth-provider a", function () {
            onProviderClick( $(this) );
            return false;
        });

        $(document).on("click", ".comment__btn", function() {
            setReplyID( $(this) );
            return false;
        });

        $(document).on("click", ".feedback-form__resetreplyto", function() {
            unsetReplyID();
            return false;
        });

        $form.submit( function() {
			submitForm();
            return false;
        });

		$('.comment__photos').each(function() { // the containers for all your galleries
			$(this).magnificPopup({
				delegate: 'a', // the selector for gallery item
				type: 'image',
				gallery: {
				  enabled:true
				}
			});
		});
    };

    var submitForm = function() {
        clearErrors();
        addReview();
    };

    var unsetReplyID = function() {
        var $form = $("#s-reviews-form"),
            $input =  $form.find("input[name=\"parent_id\"]");

        $form.find(".rev-form__f-row_rating").removeClass("is-hidden");
		$input.val("");
		if(!$(".comments-sec__form").hasClass("is-static"))
			$(".comments-sec__form").addClass("is-hidden").append($form);
    };

    var setReplyID = function( $link ) {
        var $review = $link.closest(".comment"),
            parent_id = $review.data("id"),
            $form = $("#s-reviews-form"),
            $input =  $form.find("input[name=\"parent_id\"]");

        $form.find(".rev-form__f-row_rating").addClass("is-hidden");
		// Set Form data
        $input.val(parent_id);
        // Show form and notification
		//showForm();
        $link.after($form);
        // Animate
		$('html, body').animate({
			scrollTop: ($($form).offset().top)-50
		},300);
    };

    var onProviderClick = function( $link ) {
        if (!$link.hasClass('selected')) {
            $link.siblings(".selected")
                .removeClass("selected");

            $link.addClass('selected');

            var provider_name = $link.attr('data-provider');

            if (provider_name == 'guest') {
                $('.provider-fields').hide();
                $('.provider-fields[data-provider=guest]').show();
            }

            if (provider_name == current_provider) {
                $(".provider-fields").hide();
                $(".provider-fields[data-provider='+provider_name+']").show();

            }

            // Set input
            $form.find('input[name=auth_provider]').val(provider);

            window.open( $(this).attr('href'), "oauth");
        }
    };

    var clearReviewForm = function() {
		unsetReplyID();
		clearErrors();
		refreshCaptcha();
		$(".js-errors-section").html("");
		$("#js-review-images-section .js-delete-file").each(function(){
			$(this).trigger('click');
		});
		$form.find("input, textarea").val("");
		$form.find(".rate-it__wrapper rate-it__star_js:last-child").click();
    };

    var addReview = function(form) {
		var href = $form.attr('action'),
			form_data = getData($form),
			$button = $form.find(".rev-form__btn");
		
		$error_wrapper.addClass("is-hidden");
		$button.attr("disabled","disabled");
		$(".js-reviews-form-wrapper").addClass("is-loading");

		return $.ajax({
			url: href,
			data: form_data,
			cache: false,
			contentType: false,
			processData: false,
			type: 'POST',
			success: onSuccess,
			error: function(jqXHR, errorText) {
				if (console) {
					console.error("Error", errorText);
				}
			}
		});

		function getData($form) {
			var fields_data = $form.serializeArray(),
				form_data = new FormData();

			$.each(fields_data, function () {
				var field = $(this)[0];
				form_data.append(field.name, field.value);
			});

			var $image_section = $form.find("#js-review-images-section");
			if ($image_section.length) {
				var controller = $image_section.data("controller"),
					data = controller.getSerializedArray();

				$.each(data, function(i, file_data) {
					form_data.append(file_data.name, file_data.value);
				});
			}

			return form_data;
		}

		function onSuccess(r) {
			if (r.status === "fail") {
				showErrors($form, r.errors);
				refreshCaptcha();
			} else {
				var is_reply = false;
				if(r.data.parent_id != "0" || r.data.parent_id > 0) {
					var tmp = $('<div></div>').html(r.data.html);
					$('#s-reviews-list .comment[data-id="'+r.data.parent_id+'"]').append(tmp);
				} else {
					var tmp = $('<div></div>').html(r.data.html);
					if($('#s-reviews-list').length)
						$('#s-reviews-list').prepend(tmp);
					else
						location.href = location.protocol + "//" + location.host + $form.data('redirect-url');
				}
				// update title with new count
				if($(".reviews__stat-title").length)
					$(".reviews__stat-title").text(r.data.review_count_str);
				clearReviewForm();
				$form_wrapper.closest('.item-info-feedback-form').hide();
				$('html, body').animate({
					scrollTop: ($('#s-reviews-list .comment[data-id="'+r.data.id+'"]').offset().top)-50
				},700);
				$('.comment__photos-'+r.data.id).magnificPopup({
					delegate: 'a',
					type: 'image',
					gallery: {
					  enabled:true
					}
				});
			}
			$button.removeAttr("disabled");
			$(".js-reviews-form-wrapper").removeClass("is-loading");
		}
	};

    var clearErrors = function() {
		// remove error messages
		$form.find("div.errormsg").each(function(){
			$(this).remove();
		});
		// remove red borders
		$form.find(".error").each(function(){
			$(this).removeClass("error");
		});
    };

    var showErrors = function($form, errors) {
		console.log(errors);
        for (var name in errors) {
            var $error = $("<div class=\"errormsg\" />");
            $error.text(errors[name]);
			if(name=="captcha") {
				$form.find(".wa-captcha").append("<div class='errormsg'>"+errors[name]+"</div>");
				$form.find(".wa-captcha").find("input").addClass("error");
			} else if(name=="service_agreement") {
				$form.find("#review-"+name).after("<div class='errormsg'>"+errors[name]+"</div>");
			} else {
				$form.find("#review-"+name).addClass("error").after("<div class='errormsg'>"+errors[name]+"</div>");
			}
        }
    };

    var showForm = function() {
        $('.comments-sec__form').removeClass("is-hidden");
		// scrollTo form
		$('html, body').animate({
			scrollTop: ($('.comments-sec__form').offset().top - 50)
		},700);
    };

    var closeForm = function() {
        var formWrapper = $form_wrapper.closest('.comments-sec__form');
		if(formWrapper.length) {
			formWrapper.addClass("is-hidden");
		}
    };

    var setRating = function( $link ) {
        var $wrapper = $link.closest(".rate-it__wrapper"),
            $input = $wrapper.find("input[name=\"rate\"]"),
            rate_count = $link.data("rate-count"),
            $links = $wrapper.find(".rate-it__star_js"),
            full_rate_class = "star-colour";

		$links.removeClass("animate");
        if (rate_count && rate_count > 0) {
            // SET RATING
                // Clear old styles
                $links.find(".full").removeClass(full_rate_class);

                for ( var i = 0; i < rate_count; i++ ) {
                    $($links[i]).addClass("animate").find(".full").addClass(full_rate_class);
                }

            // SET FIELD VALUE
            $input.val(rate_count);
        }
    };

    var refreshCaptcha = function() {
        $(".rev-form__captcha-img img").trigger("click");
    };

    $(document).ready( function() {
        reviews_initialize();
    });

})(jQuery);

