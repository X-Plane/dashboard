# X-Plane Usage Data Dashboard

This is a webapp for displaying X-Plane Desktop's usage analytics.

It uses the [Dash (by Plotly)](https://plot.ly/products/dash/) framework to produce interactive graphs.

See it live at [dashboard.x-plane.com](http://dashboard.x-plane.com).

## Deployment

We deploy via [Dokku](http://dokku.viewdocs.io/dokku/) (a self-hosted Heroku-like PaaS, which we run on Digital Ocean). You can Git push to `ssh://dokku@dashboard.x-plane.com/dashboard` and Dokku will handle the deploy for you:

    $ git remote add dokku ssh://dokku@dashboard.x-plane.com/dashboard
    $ git push dokku

